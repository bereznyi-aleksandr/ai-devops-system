#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_seal.py
# ВЕРСИЯ: v0.2 (выпуск B10)  СТАТУС: DRAFT  ДАТА ОБНОВЛЕНИЯ: 2026-11-14 23:28 +02:00
# ДАТА СОЗДАНИЯ: 2026-11-14 23:23 +02:00  ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · напарник · 03» (d6c11f6b)
# НАЗНАЧЕНИЕ: проверки zprobe_seal.py (проект B10 v0.18 разделы 4.3 и 4.4). Каждая проверка — одно нарушение.
#   Печатает CASE <имя> PASS/FAIL (или SKIP) и итог ZPROBE_SEAL_TEST=PASS/FAIL.
#   Части S01–S27, S41–S42 — без файловой системы, идут везде. S28–S40, S43–S55 — папки, права и порядок печати 4.4
#   (SQL — подставные функции): только Linux от root
#   (в CI — под sudo); корень испытаний — новая папка в /var/lib (каждый шаг пути root без записи g/o, как SEAL_ROOT).
#   Без root эти части печатают SKIP, а итог — ZPROBE_SEAL_TEST=PASS_NO_ROOT (для CI не годится).
# ЗАПУСК: python3 -I -B test_zprobe_seal.py   (CI: sudo python3 -I -B …)
import hashlib
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zprobe_seal as Z  # noqa: E402

OK = True
SKIPPED = 0
BOOT = 'bc77431f' + '0' * 24
LID = '0123abcd-0000-4000-8000-00000000c0de'
CUR1 = f's={"a" * 32};i=1f;b={BOOT};m=2a;t=5f1;x=9'
CUR2 = f's={"a" * 32};i=20;b={BOOT};m=2b;t=5f2;x=a'
NAMES = ['anchor.json', 'dropin_50-zprobe.conf', 'evidence.json', 'request.json', 'state.json']


def case(name, cond):
    global OK
    OK &= bool(cond)
    print('CASE', name, 'PASS' if cond else 'FAIL', flush=True)


def refused(fn, *a, want=None):
    """True, если вызов дал Refused (и, если задано, с нужным началом причины)."""
    try:
        fn(*a)
    except Z.Refused as e:
        return want is None or str(e).startswith(want)
    return False


def proof(**kw):
    p = {'version': 1, 'series': 'pb1trial2', 'lease_id': LID, 'boot_id': BOOT, 't0_utc': '2026-11-14T08:00:00Z',
         'checks': {f'H{i}': {'ok': True, 'value': f'n={i} OK'} for i in range(1, 11)},
         'journal_from_cursor': CUR1, 'journal_to_cursor': CUR2,
         'sources': [{'name': n, 'sha256': hashlib.sha256(n.encode()).hexdigest(), 'size': 10} for n in NAMES],
         'inventory_sha256': 'b' * 64, 'preserve_manifest_sha256': 'c' * 64, 'tool_version': 'b10-0.1',
         'created_utc': '2026-11-14T21:00:00Z'}
    p['checks']['H9'] = {'ok': True, 'value': 'OK', 'src': 'r1'}
    p.update(kw)
    return p


def chk(obj=None, raw=None, series='pb1trial2', lid=LID, names=NAMES):
    return Z.check_proof(raw if raw is not None else Z.canon(obj), series, lid, names)


# ---- канон и закрытая схема (4.3) ----
c = Z.canon({'b': 1, 'a': [1, 'я']})
case('S01 canon: sorted keys, no spaces, ascii escapes, no final newline', c == b'{"a":[1,"\\u044f"],"b":1}')
case('S02 good proof passes', chk(proof())['series'] == 'pb1trial2')
case('S03 extra field -> proof_fields', refused(chk, dict(proof(), extra=1), want='proof_fields'))
p = proof()
del p['tool_version']
case('S04 missing field -> proof_fields', refused(chk, p, want='proof_fields'))
case('S05 non-canonical bytes (spaces) -> proof_not_canonical',
     refused(chk, None, json.dumps(proof(), sort_keys=True).encode(), want='proof_not_canonical'))
case('S06 final newline -> proof_not_canonical',
     refused(chk, None, Z.canon(proof()) + b'\n', want='proof_not_canonical'))
case('S07 other series -> proof_series', refused(chk, proof(series='pb1trial3'), want='proof_series'))
case('S08 other lease_id -> proof_lease_id',
     refused(chk, proof(lease_id=LID[:-1] + 'f'), want='proof_lease_id'))
case('S09 version true (bool) -> proof_version', refused(chk, proof(version=True), want='proof_version'))
case('S10 cursor of other boot -> proof_cursor_boot',
     refused(chk, proof(journal_to_cursor=CUR2.replace(BOOT, 'd' * 32)), want='proof_cursor_boot'))
p = proof()
del p['checks']['H10']
case('S11 no H10 -> proof_checks', refused(chk, p, want='proof_checks'))
p = proof()
p['checks']['H3']['ok'] = False
case('S12 H3 ok=false -> proof_check_H3', refused(chk, p, want='proof_check_H3'))
p = proof()
p['checks']['H9'] = {'ok': True, 'value': 'OK', 'src': 'disk'}
case('S13 H9 src not r1|run -> proof_check_H9', refused(chk, p, want='proof_check_H9'))
p = proof()
p['checks']['H5']['value'] = 'free text here'
case('S14 value outside fixed format -> proof_check_H5', refused(chk, p, want='proof_check_H5'))
p = proof()
p['sources'] = list(reversed(p['sources']))
case('S15 sources not sorted -> proof_sources_matrix', refused(chk, p, want='proof_sources_matrix'))
p = proof()
p['sources'] = p['sources'][1:]
case('S16 source missing from matrix -> proof_sources_matrix', refused(chk, p, want='proof_sources_matrix'))
p = proof()
p['sources'] = sorted(p['sources'] + [p['sources'][0]], key=lambda s: s['name'])
case('S17 duplicate source -> proof_sources_matrix', refused(chk, p, want='proof_sources_matrix'))
p = proof()
p['sources'][0]['size'] = True
case('S18 source size bool -> proof_source_entry', refused(chk, p, want='proof_source_entry'))
case('S19 preserve_manifest_sha256 null accepted (cleanup)', chk(proof(preserve_manifest_sha256=None)) is not None)
case('S20 preserve_manifest_sha256 short -> refused',
     refused(chk, proof(preserve_manifest_sha256='c' * 63), want='proof_preserve_manifest_sha256'))
case('S21 over 256 KiB -> proof_size', refused(chk, None, b' ' * (Z.MAX_PROOF + 1), want='proof_size'))
case('S22 non-ascii bytes -> proof_json', refused(chk, None, '{"а":1}'.encode('utf-8'), want='proof_json'))

# ---- матрица и опись (4.3, грамматика B) ----
case('S23 matrix: cleanup drops only cleanup.json, r2 only MANIFEST.sha256, other kind refused',
     Z.matrix('cleanup', ['b', 'cleanup.json', 'a']) == ['a', 'b']
     and Z.matrix('r2', ['MANIFEST.sha256', 'cleanup.json']) == ['cleanup.json']
     and refused(Z.matrix, 'run', ['a'], want='matrix_kind'))
L1 = Z.inventory_line('a' * 64, 12, 'anchor.json', '/var/lib/zavod/preserve/pb1trial2/anchor.json', '-',
                      '0:0:0600', '-')
L2 = Z.inventory_line('b' * 64, 0, 'state.json', '/var/lib/zavod/preserve/pb1trial2/state.json',
                      '/run/zprobe/pb1trial2/state.json', '0:0:0600', '0:1001:0640')
inv = (L1 + L2).encode()
case('S24 inventory: line grammar and round trip',
     L1.count('  ') == 6 and Z.parse_inventory(inv) == {'anchor.json': ('a' * 64, 12), 'state.json': ('b' * 64, 0)})
case('S25 inventory: lines out of name order -> inventory_order',
     refused(Z.parse_inventory, (L2 + L1).encode(), want='inventory_order'))
case('S26 inventory: CRLF or no final newline -> inventory_eol',
     refused(Z.parse_inventory, (L1 + L2).replace('\n', '\r\n').encode(), want='inventory_eol')
     and refused(Z.parse_inventory, inv[:-1], want='inventory_eol'))
case('S27 inventory: size with leading zero -> inventory_line',
     refused(Z.parse_inventory, L1.replace('  12  ', '  012  ').encode(), want='inventory_line'))
case('S41 inventory: orig=- only together with orig_src=- (anchor.json, B9 R2)',
     refused(Z.inventory_line, 'a' * 64, 1, 'anchor.json', '/p/anchor.json', '-', '0:0:0600', '0:0:0600',
             want='inventory_field')
     and refused(Z.inventory_line, 'a' * 64, 1, 'anchor.json', '/p/anchor.json', '/r/anchor.json', '0:0:0600', '-',
                 want='inventory_field'))
case('S42 inventory: orig=- for a name other than anchor.json -> inventory_field',
     refused(Z.inventory_line, 'a' * 64, 1, 'state.json', '/p/state.json', '-', '0:0:0600', '-',
             want='inventory_field'))

# ---- папки, права, попытки (4.3, 4.4) — только Linux от root ----
FS = os.name == 'posix' and hasattr(os, 'geteuid') and os.geteuid() == 0
FS_CASES = ['S28 open_root accepts root chain', 'S29 group-writable dir -> dir_owner',
            'S30 dir owned by uid 65534 -> dir_owner', 'S31 symlink dir -> OSError (no follow)',
            'S32 new_attempt: k=1 then k=2, mode 0700', 'S33 new_attempt after 1 and 5 -> 6 (max+1)',
            'S34 attempts: bad name, plain file, symlink -> attempt_name',
            'S35 write_proof: sha of canon bytes, 0600, second write refused (O_EXCL)',
            'S36 read_small: mode 0644 -> file_mode', 'S37 read_small: owner 65534 -> file_mode',
            'S38 read_small: symlink -> OSError', 'S39 find_retry: only matching attempts, no-proof skipped',
            'S40 new_attempt at 9999 -> attempts_exhausted',
            'S43 seal first: SEALED_NOW, k=1, src/ snapshot + INVENTORY, sum = proof.json',
            'S44 seal retry with row: ALREADY_SEALED, same k, no new attempt',
            'S45 /run changed after seal (state rewritten, cleanup.json added): retry still ALREADY_SEALED',
            'S46 call lost before COMMIT, no row: next seal takes k=2, k=1 untouched',
            'S47 COMMIT done but answer lost: next seal -> ALREADY_SEALED from k=1, no k=2',
            'S48 snapshot file tampered: retry -> REFUSED_INCONSISTENT, no SQL call',
            'S49 two attempts with the row sum: retry -> REFUSED_INCONSISTENT',
            'S50 H1-H10 not ok: BLOCKED_SESSION_UNKNOWN, no attempt folder',
            'S51 recheck H8/H10 fails after freeze: BLOCKED, src/ kept, no proof.json, no SQL call',
            'S52 SELECT lease_seal fails: BLOCKED, nothing created',
            'S53 extra file in source outside the matrix: BLOCKED src_matrix_before, no proof',
            'S54 row with other series: REFUSED_INCONSISTENT',
            'S55 fixed src 0:0:0600 but source 0644 (B9 R2 rule): BLOCKED src_mode']
if not FS:
    for n in FS_CASES:
        print('CASE', n.split(' ', 1)[0], n.split(' ', 1)[1], 'SKIP (needs Linux root)', flush=True)
        SKIPPED += 1
else:
    base = tempfile.mkdtemp(prefix='zseal-test-', dir='/var/lib')
    os.chmod(base, 0o755)
    rfd = Z.open_root(base)
    case(FS_CASES[0], isinstance(rfd, int))
    os.mkdir('gw', dir_fd=rfd)
    os.chmod('gw', 0o770, dir_fd=rfd)
    case(FS_CASES[1], refused(Z.open_dir, 'gw', rfd, want='dir_owner'))
    os.mkdir('nb', 0o755, dir_fd=rfd)
    os.chown('nb', 65534, 65534, dir_fd=rfd)
    case(FS_CASES[2], refused(Z.open_dir, 'nb', rfd, want='dir_owner'))
    os.mkdir('real', 0o755, dir_fd=rfd)
    os.symlink('real', 'link', dir_fd=rfd)
    try:
        Z.open_dir('link', rfd)
        followed = True
    except OSError:
        followed = False
    case(FS_CASES[3], not followed)

    os.mkdir('s1', 0o700, dir_fd=rfd)
    s1 = Z.open_dir('s1', rfd)
    k1, a1 = Z.new_attempt(s1)
    k2, a2 = Z.new_attempt(s1)
    case(FS_CASES[4], (k1, k2) == (1, 2) and os.fstat(a2).st_mode & 0o777 == 0o700)
    os.mkdir('s2', 0o700, dir_fd=rfd)
    s2 = Z.open_dir('s2', rfd)
    os.mkdir('1', 0o700, dir_fd=s2)
    os.mkdir('5', 0o700, dir_fd=s2)
    k6, a6 = Z.new_attempt(s2)
    case(FS_CASES[5], k6 == 6)

    bad = []
    for n, make in (('s3', lambda d: os.mkdir('07', 0o700, dir_fd=d)),
                    ('s4', lambda d: os.close(os.open('3', os.O_CREAT | os.O_WRONLY, 0o600, dir_fd=d))),
                    ('s5', lambda d: (os.mkdir('1', 0o700, dir_fd=d), os.symlink('1', '4', dir_fd=d)))):
        os.mkdir(n, 0o700, dir_fd=rfd)
        d = Z.open_dir(n, rfd)
        make(d)
        bad.append(refused(Z.attempts, d, want='attempt_name'))
    case(FS_CASES[6], all(bad))

    obj = proof()
    sha = Z.write_proof(a1, obj)
    st = os.stat('proof.json', dir_fd=a1)
    try:
        Z.write_proof(a1, obj)
        second = True
    except FileExistsError:
        second = False
    case(FS_CASES[7], sha == hashlib.sha256(Z.canon(obj)).hexdigest() and st.st_mode & 0o777 == 0o600
         and not second and Z.read_small('proof.json', a1) == Z.canon(obj))

    def small(name, mode, uid=0):
        fd = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600, dir_fd=a2)
        os.write(fd, b'x')
        os.fchmod(fd, mode)
        os.fchown(fd, uid, uid)
        os.close(fd)

    small('m644', 0o644)
    case(FS_CASES[8], refused(Z.read_small, 'm644', a2, want='file_mode'))
    small('nobody', 0o600, 65534)
    case(FS_CASES[9], refused(Z.read_small, 'nobody', a2, want='file_mode'))
    os.symlink('m644', 'lnk', dir_fd=a2)
    try:
        Z.read_small('lnk', a2)
        followed = True
    except OSError:
        followed = False
    case(FS_CASES[10], not followed)

    # s1: попытка 1 — proof A, попытка 2 — без proof, попытка 3 — proof B, попытка 4 — снова A
    k3, a3 = Z.new_attempt(s1)
    shb = Z.write_proof(a3, proof(tool_version='b10-0.2'))
    k4, a4 = Z.new_attempt(s1)
    Z.write_proof(a4, obj)
    case(FS_CASES[11], Z.find_retry(s1, shb) == [3] and Z.find_retry(s1, 'e' * 64) == []
         and Z.find_retry(s1, sha) == [1, 4])

    os.mkdir('s6', 0o700, dir_fd=rfd)
    s6 = Z.open_dir('s6', rfd)
    os.mkdir('9999', 0o700, dir_fd=s6)
    case(FS_CASES[12], refused(Z.new_attempt, s6, want='attempts_exhausted'))

    # ---- общий порядок печати 4.4 (SQL — подставные функции) ----
    os.mkdir('seal', 0o755, dir_fd=rfd)
    SEAL = base + '/seal'
    RUN = ['anchor_run.json', 'evidence.json', 'request.json', 'state.json']

    def mkrun(tag, extra=(), mode=0o644):
        os.mkdir(tag, 0o755, dir_fd=rfd)
        d = Z.open_dir(tag, rfd)
        for n in RUN + list(extra):
            fd = os.open(n, os.O_CREAT | os.O_EXCL | os.O_WRONLY, mode, dir_fd=d)
            os.write(fd, ('{"n":"%s"}' % n).encode())
            os.fchmod(fd, mode)
            os.close(fd)
        os.close(d)
        path = base + '/' + tag

        def opener():
            return Z.open_dir(path), path, {n: (None, None) for n in RUN}
        return path, opener

    class DB:
        def __init__(self, fail=None):
            self.row, self.calls, self.fail = None, [], fail

        def select(self, lid):
            if self.fail == 'select':
                raise RuntimeError('psql rc 2')
            return self.row

        def call(self, s, lid, sha):
            self.calls.append(sha)
            if self.fail == 'lost_before':
                self.fail = None
                raise RuntimeError('connection lost')
            if self.row is None:
                self.row = {'series': s, 'proof_sha256': sha}
                if self.fail == 'lost_after':
                    self.fail = None
                    raise RuntimeError('connection lost')
                return 'SEALED_NOW'
            return 'ALREADY_SEALED' if self.row['proof_sha256'] == sha else 'REFUSED_INCONSISTENT'

    GOOD = {'ok': True, 'checks': proof()['checks'], 'boot_id': BOOT, 't0_utc': '2026-11-14T08:00:00Z',
            'journal_from_cursor': CUR1, 'journal_to_cursor': CUR2}

    def go(series, db, opener, checks=GOOD, rc=True, fixed=None):
        return Z.seal('cleanup', series, LID, db.select, db.call, lambda: checks, lambda: rc, opener, 'b10-0.1',
                      lambda: '2026-11-14T21:30:00Z', None, fixed, SEAL)

    def ks(series):
        return sorted(os.listdir(f'{SEAL}/{series}')) if os.path.isdir(f'{SEAL}/{series}') else []

    pa, oa = mkrun('run_a')
    db = DB()
    r1 = go('sa', db, oa)
    with open(f'{SEAL}/sa/1/proof.json', 'rb') as f:
        psha = hashlib.sha256(f.read()).hexdigest()
    case(FS_CASES[13], r1['result'] == 'SEALED_NOW' and r1['k'] == 1 and r1['sha'] == psha == db.row['proof_sha256']
         and sorted(os.listdir(f'{SEAL}/sa/1/src')) == sorted(RUN + ['INVENTORY.sha256']))
    r2 = go('sa', db, oa)
    case(FS_CASES[14], r2['result'] == 'ALREADY_SEALED' and r2['k'] == 1 and ks('sa') == ['1'])
    with open(pa + '/state.json', 'w') as f:
        f.write('{"final":1}')
    with open(pa + '/cleanup.json', 'w') as f:
        f.write('{}')
    case(FS_CASES[15], go('sa', db, oa)['result'] == 'ALREADY_SEALED' and ks('sa') == ['1'])

    pb, ob = mkrun('run_b')
    db = DB('lost_before')
    try:
        go('sb', db, ob)
        raised = False
    except RuntimeError:
        raised = True
    with open(f'{SEAL}/sb/1/proof.json', 'rb') as f:
        k1raw = f.read()
    r = go('sb', db, ob)
    with open(f'{SEAL}/sb/1/proof.json', 'rb') as f:
        k1same = f.read() == k1raw
    case(FS_CASES[16], raised and r['result'] == 'SEALED_NOW' and r['k'] == 2 and ks('sb') == ['1', '2'] and k1same)

    pc, oc = mkrun('run_c')
    db = DB('lost_after')
    try:
        go('sc', db, oc)
    except RuntimeError:
        pass
    r = go('sc', db, oc)
    case(FS_CASES[17], r['result'] == 'ALREADY_SEALED' and r['k'] == 1 and ks('sc') == ['1'])

    pd, od = mkrun('run_d')
    db = DB()
    go('sd', db, od)
    with open(f'{SEAL}/sd/1/src/request.json', 'ab') as f:
        f.write(b' ')
    n0 = len(db.calls)
    r = go('sd', db, od)
    case(FS_CASES[18], r['result'] == 'REFUSED_INCONSISTENT' and len(db.calls) == n0)

    pe, oe = mkrun('run_e')
    db = DB()
    go('se', db, oe)
    sfd = Z.open_dir('se', Z.open_root(SEAL))
    k2, a2e = Z.new_attempt(sfd)
    with open(f'{SEAL}/se/1/proof.json', 'rb') as f:
        Z.put_excl('proof.json', f.read(), a2e)
    r = go('se', db, oe)
    case(FS_CASES[19], r['result'] == 'REFUSED_INCONSISTENT' and 'retry_hits:2' in r['reason'])

    pf, of = mkrun('run_f')
    db = DB()
    r = go('sf', db, of, checks=dict(GOOD, ok=False))
    case(FS_CASES[20], r['result'] == 'BLOCKED_SESSION_UNKNOWN' and ks('sf') == [] and db.calls == [])

    pg, og = mkrun('run_g')
    db = DB()
    r = go('sg', db, og, rc=False)
    case(FS_CASES[21], r['result'] == 'BLOCKED_SESSION_UNKNOWN' and ks('sg') == ['1'] and db.calls == []
         and os.path.isdir(f'{SEAL}/sg/1/src') and not os.path.exists(f'{SEAL}/sg/1/proof.json'))

    ph, oh = mkrun('run_h')
    db = DB('select')
    r = go('sh', db, oh)
    case(FS_CASES[22], r['result'] == 'BLOCKED_SESSION_UNKNOWN' and ks('sh') == [] and db.calls == [])

    pi, oi = mkrun('run_i', extra=['surprise.json'])
    db = DB()
    r = go('si', db, oi)
    case(FS_CASES[23], r['result'] == 'BLOCKED_SESSION_UNKNOWN' and 'src_matrix_before' in r['reason']
         and db.calls == [] and not os.path.exists(f'{SEAL}/si/1/proof.json'))

    pj, oj = mkrun('run_j')
    db = DB()
    go('sj', db, oj)
    db.row = dict(db.row, series='other')
    case(FS_CASES[24], go('sj', db, oj)['result'] == 'REFUSED_INCONSISTENT')

    pk, ok_ = mkrun('run_k')
    db = DB()
    r = go('sk', db, ok_, fixed='0:0:0600')
    case(FS_CASES[25], r['result'] == 'BLOCKED_SESSION_UNKNOWN' and 'src_mode' in r['reason'] and db.calls == [])

if not OK:
    print('ZPROBE_SEAL_TEST=FAIL')
    sys.exit(1)
print('ZPROBE_SEAL_TEST=' + ('PASS' if SKIPPED == 0 else 'PASS_NO_ROOT'))
