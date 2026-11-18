# ДОКУМЕНТ: zavod/ops/operator/test_d17_v0_2_fixture.py — подставные файлы сервера для CI-задания b12-d17-readonly
#   (команда D17 v0.2; только для испытания на одноразовой машине CI, на сервере не запускается)
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-18 09:46 +02:00  ИСПОЛНИТЕЛЬ: Claude (терминал zavod, пускатель)
# build <T> (root): заново создаёт R2_OUT, r2obs/pb1trial2 (свой obs и второй, как от прежнего R2), seal/pb1trial2/1
#   (proof.json, src с описью; в одном файле src — номер аренды и SRC_SECRET_MARKER) и чужую серию seal/otherseries
#   (FOREIGN_MARKER); все байты постоянные, поэтому суммы при каждой сборке одни и те же; суммы — в <T>/pin.json.
# prog <T> <программа> <строка>: тестовая программа = боевая, у которой заменён ТОЛЬКО блок PIN (между # PIN-BEGIN и
#   # PIN-END); тестовая строка = боевая, у которой заменены ТОЛЬКО N= и S=. Пишет <T>/stub/prog.py и <T>/line_test.sh.
import hashlib
import json
import os
import shutil
import sys

LID = '11111111-2222-4333-8444-555555555555'
X = '/root/zprobe-b12-r2-1d4d2caf62e0-20261118T061742Z-505172/zprobe-r2-b12-pb1trial2.out'
Z = '/var/lib/zavod'
SEAL = Z + '/seal'
OBSD = Z + '/r2obs/pb1trial2'


def canon(o):
    return json.dumps(o, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def put(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.write(fd, data)
    os.close(fd)
    os.chmod(path, 0o600)


def build(t):
    os.umask(0o077)
    for p in (os.path.dirname(X), Z, '/root/secret.txt'):
        if os.path.isdir(p) and not os.path.islink(p):
            shutil.rmtree(p)
        elif os.path.lexists(p):
            os.unlink(p)
    os.mkdir(Z, 0o755)
    os.chmod(Z, 0o755)
    for p in (os.path.dirname(X), OBSD, SEAL + '/pb1trial2/1/src', SEAL + '/otherseries/1'):
        os.makedirs(p, 0o700)
    src = {'anchor.json': b'{"a":1}\n', 'zagent.env': f'LEASE={LID}\nSRC_SECRET_MARKER=1\n'.encode()}
    lines, sources = [], []
    for n in sorted(src):
        d = src[n]
        put(f'{SEAL}/pb1trial2/1/src/{n}', d)
        orig, osrc = ('-', '-') if n == 'anchor.json' else ('/home/zagent/zagent.env', '0:0:0640')
        lines.append(f'{sha(d)}  {len(d)}  {n}  phys={Z}/preserve/pb1trial2/{n}  orig={orig}  src=0:0:0600  '
                     f'orig_src={osrc}\n')
        sources.append({'name': n, 'sha256': sha(d), 'size': len(d)})
    inv = ''.join(lines).encode('ascii')
    put(f'{SEAL}/pb1trial2/1/src/INVENTORY.sha256', inv)
    obs = canon({'jd': {'rx': 2}, 'lid_sha': sha(LID.encode())}).encode('ascii')
    osha = sha(obs)
    put(f'{OBSD}/obs-{osha}.json', obs)
    old = b'{"old":"b11"}'
    put(f'{OBSD}/obs-{sha(old)}.json', old)
    checks = {f'H{i}': {'ok': True, 'value': 'v'} for i in range(1, 11)}
    checks['H4'] = {'ok': True, 'value': f'obs={osha}'}
    checks['H5'] = {'ok': True, 'value': f'n=1 obs={osha}'}
    checks['H9'] = {'ok': True, 'value': 'v', 'src': 'run'}
    proof = {'version': 1, 'series': 'pb1trial2', 'lease_id': LID, 'boot_id': '0' * 32, 't0_utc': '2026-11-18T06:17:42Z',
             'checks': checks, 'journal_from_cursor': 'c1', 'journal_to_cursor': 'c2', 'sources': sources,
             'inventory_sha256': sha(inv), 'preserve_manifest_sha256': '1' * 64, 'tool_version': 'zprobe-TOOLMARK',
             'created_utc': '2026-11-18T06:17:50Z'}
    pr = canon(proof).encode('ascii')
    put(f'{SEAL}/pb1trial2/1/proof.json', pr)
    psha = sha(pr)
    put(f'{SEAL}/otherseries/1/proof.json', b'FOREIGN_MARKER')
    diag = {'state': 'PRIMARY_CHECKS', 'ok': {f'H{i}': True for i in range(1, 11)}, 'obs_sha': osha}
    out = (f'R2=SEALED_NOW status=SAFE_PRE_START k=1 sha={psha} failed=- reason=first\n'
           f'R2_OBS {obs.decode()}\n'
           f'R2_OBS_FILE {Z}/r2obs/pb1trial2/obs-{osha}.json sha={osha}\n'
           f'R2_OBS_CHECK ok {osha}\n'
           f'R2_DIAG {canon(diag)}\n').encode('ascii')
    put(X, out)
    pin = {'r2_out': X, 'r2_out_size': len(out), 'r2_out_sha': sha(out), 'proof_sha': psha,
           'lid_sha': sha(LID.encode()), 'obs_sha': osha}
    with open(t + '/pin.json', 'w') as f:
        json.dump(pin, f, sort_keys=True)
    os.chmod(t + '/pin.json', 0o644)
    print('FIXTURE_OK', canon(pin))


def prog(t, prod_prog, prod_line):
    p = open(prod_prog, 'rb').read()
    a, b = b'# PIN-BEGIN\n', b'# PIN-END\n'
    assert p.count(a) == 1 and p.count(b) == 1
    i, j = p.index(a) + len(a), p.index(b)
    pin = json.load(open(t + '/pin.json'))
    tp = p[:i] + ('PIN = ' + repr(pin) + '\n').encode('ascii') + p[j:]
    assert tp[:i] == p[:i] and tp[-(len(p) - j):] == p[j:]
    os.makedirs(t + '/stub', exist_ok=True)
    open(t + '/stub/prog.py', 'wb').write(tp)
    line = open(prod_line, 'rb').read()
    old = f'; N={len(p)}; S={sha(p)}; '.encode()
    assert line.count(old) == 1, 'line does not pin the program file'
    open(t + '/line_test.sh', 'wb').write(line.replace(old, f'; N={len(tp)}; S={sha(tp)}; '.encode()))
    print('PROG_OK', len(tp), sha(tp))


if __name__ == '__main__':
    if sys.argv[1] == 'build':
        build(sys.argv[2])
    else:
        prog(sys.argv[2], sys.argv[3], sys.argv[4])
