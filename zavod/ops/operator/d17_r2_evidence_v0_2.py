# ДОКУМЕНТ: zavod/ops/operator/d17_r2_evidence_v0_2.py — программа команды оператора D17 v0.2: ТОЛЬКО ЧТЕНИЕ
#   доказательств второго R2 B12 (шаг 3.5.5 ПБ-1; REL119 M-355-REL119-01; REL120 REVISE M-01, M-02, L-01)
# ВЕРСИЯ: v0.2  СТАТУС: DRAFT (не выдавать оператору до независимого аудита)
# ДАТА СОЗДАНИЯ: 2026-11-18 09:46 +02:00  ИСПОЛНИТЕЛЬ: Claude (терминал zavod, пускатель)
# КАК ЗАПУСКАЕТСЯ: последняя строка cmd_b12_d17_r2_evidence_readonly_v0_2.sh скачивает этот файл В ПАМЯТЬ (на диск не
#   пишет) с raw.githubusercontent.com по закреплённому коммиту, сверяет размер и SHA-256 с закреплёнными в строке и только
#   тогда выполняет байты в /usr/bin/python3 -I -B; иначе — REFUSED, ничего не выполнено (CI сверяет: файл в коммите = N, S).
# ПРАВИЛО ЧТЕНИЯ (M-01): каждый каталог пути — от «/» по дескриптору, без ссылок (O_NOFOLLOW), root:root, без записи
#   группы и всех; каждый файл — O_NOFOLLOW|O_NONBLOCK (FIFO не вешает), по fstat обычный, root:root 0600, одна ссылка,
#   размер не больше предела; содержимое печатается ТОЛЬКО если SHA-256 равна закреплённой (R2_OUT, proof.json) или
#   закреплена цепочкой от proof (опись INVENTORY.sha256). Записи r2obs, не подходящие под obs-<64hex>.json и обычный
#   файл, — строка OBS_SKIP без открытия. В seal читается только серия pb1trial2 (другие серии не перечисляются).
# СВЕРКА СНИМКА (M-02, как zprobe_seal.verify_attempt): серия — ровно попытка 1; попытка — ровно proof.json и src;
#   SHA-256 описи = proof.inventory_sha256; опись по грамматике B; {имя: (SHA, размер)} описи = proof.sources; состав
#   src = имена + INVENTORY.sha256; каждый src/<имя> — размер и SHA-256 = опись и proof; phys = preserve/pb1trial2/<имя>.
#   Содержимое src не печатается (только имя, размер, SHA-256, MATCH/DIFF).
# ИТОГ (L-01): по разделу строка SEC <раздел> PASS|FAIL; общий итог D17_OK (все проверки прошли, код 0) или
#   D17_FAIL <список> (код 1). Номер аренды не печатается никогда: перед выводом весь текст сверяется с lease_id из
#   proof; найден — печатается только D17_FAIL lease_id_in_output.
# НЕ ДЕЛАЕТ: ничего не создаёт, не пишет, не удаляет, не переименовывает; R2, печать, установку, службы не запускает.
#   База: runuser postgres psql, первым SET default_transaction_read_only = on, дальше только SELECT.
import hashlib
import json
import os
import re
import stat
import subprocess
import sys

# PIN-BEGIN
PIN = {
    'r2_out': '/root/zprobe-b12-r2-1d4d2caf62e0-20261118T061742Z-505172/zprobe-r2-b12-pb1trial2.out',
    'r2_out_size': 2703,
    'r2_out_sha': 'a529f1894438b300efd57974c75f243a13de33141be7106affbb5b8106363bbe',
    'proof_sha': '7bbed2ec8b5dc401175897e7d8fe08cd856b85816fef6f5267f99f2236ae668f',
    'lid_sha': 'ef548a9ac3f3f45e6f0b8fd3c574738a2d6fa677bedcd17f5f36739b47b3c648',
    'obs_sha': 'c2bc8618b3a0c8a6b262726efc633cf5e9dc85d6b9b0d9e5cb263d337628f5e9',
}
# PIN-END
SERIES = 'pb1trial2'
SEAL = '/var/lib/zavod/seal'
OBS = '/var/lib/zavod/r2obs'
PRESERVE = '/var/lib/zavod/preserve/' + SERIES
REASON = 'NO_SESSION_PRE_START'
FIELDS = {'version', 'series', 'lease_id', 'boot_id', 't0_utc', 'checks', 'journal_from_cursor', 'journal_to_cursor',
          'sources', 'inventory_sha256', 'preserve_manifest_sha256', 'tool_version', 'created_utc'}
CHECKS = tuple(f'H{i}' for i in range(1, 11))
HEX64 = re.compile(r'[0-9a-f]{64}')
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}')
MODE = re.compile(r'[0-9]+:[0-9]+:[0-7]{4}')
PATHRE = re.compile(r'/[A-Za-z0-9@._/-]{1,250}')
OBSNAME = re.compile(r'obs-([0-9a-f]{64})\.json')
OBS_TOKEN = re.compile(r'(?:^| )obs=([0-9a-f]{64})(?= |$)')
LIMIT = 1 << 20
SECS = ('r2_out', 'obs', 'proof', 'src', 'db', 'r2_text')
OUT = {s: [] for s in SECS}
FAIL = []


class Stop(Exception):
    """Проверка не прошла: раздел дальше не читается."""


def sha(b):
    return hashlib.sha256(b).hexdigest()


def show(name):
    """Имя записи каталога для печати: только безопасные знаки, не длиннее 80."""
    return name if NAME.fullmatch(name) else ascii(name)[:80]


def check(sec, ok, code):
    if not ok:
        FAIL.append(f'{sec}:{code}')
        OUT[sec].append(f'FAIL {code}')
    return ok


def open_dir(name, dir_fd=None):
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dir_fd)
    st = os.fstat(fd)
    if st.st_uid != 0 or st.st_gid != 0 or st.st_mode & 0o022:
        os.close(fd)
        raise Stop(f'dir_owner:{show(name)}')
    return fd, st


def open_path(path):
    fd, st = open_dir('/')
    for part in [p for p in path.split('/') if p]:
        try:
            nfd, st = open_dir(part, dir_fd=fd)
        finally:
            os.close(fd)
        fd = nfd
    return fd, st


def kind(name, dir_fd):
    m = os.stat(name, dir_fd=dir_fd, follow_symlinks=False).st_mode
    return 'dir' if stat.S_ISDIR(m) else 'file' if stat.S_ISREG(m) else 'link' if stat.S_ISLNK(m) else 'other'


def read_file(name, dir_fd, limit=LIMIT):
    """Обычный файл без ссылок, root:root 0600, одна ссылка, не больше limit; (байты, fstat)."""
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=dir_fd)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise Stop(f'not_regular:{show(name)}')
        if st.st_uid != 0 or st.st_gid != 0 or stat.S_IMODE(st.st_mode) != 0o600 or st.st_nlink != 1:
            raise Stop(f'file_mode:{show(name)}')
        if st.st_size > limit:
            raise Stop(f'file_size:{show(name)}')
        got = b''
        while len(got) <= limit:
            part = os.read(fd, 65536)
            if not part:
                break
            got += part
        if len(got) != st.st_size:
            raise Stop(f'file_changed:{show(name)}')
        return got, st
    finally:
        os.close(fd)


def meta(st):
    return f'{st.st_uid}:{st.st_gid}:{stat.S_IMODE(st.st_mode):04o} links={st.st_nlink} size={st.st_size}'


def sec_r2_out():
    o = OUT['r2_out']
    d, base = os.path.split(PIN['r2_out'])
    o.append(f'PATH {PIN["r2_out"]}')
    fd, st = open_path(d)
    try:
        o.append(f'DIR {meta(st)}')
        raw, st = read_file(base, fd, PIN['r2_out_size'])
    finally:
        os.close(fd)
    o.append(f'FILE {meta(st)}')
    h = sha(raw)
    if not check('r2_out', len(raw) == PIN['r2_out_size'] and h == PIN['r2_out_sha'], f'sha_diff {h}'):
        raise Stop('r2_out_sha')
    o.append(f'R2_OUT_SHA_MATCH {h}')
    return raw


def sec_obs():
    o = OUT['obs']
    fd, st = open_path(f'{OBS}/{SERIES}')
    try:
        o.append(f'DIR {OBS}/{SERIES} {meta(st)}')
        names = sorted(os.listdir(fd))
        o.append(f'ENTRIES {len(names)}')
        want = f'obs-{PIN["obs_sha"]}.json'
        found = False
        for n in names:
            m, t = OBSNAME.fullmatch(n), kind(n, fd)
            if not m or t != 'file':
                o.append(f'OBS_SKIP {show(n)} type={t}')
                check('obs', False, f'entry:{show(n)}')
                continue
            try:
                raw, st2 = read_file(n, fd)
            except Stop as e:
                check('obs', False, str(e))
                continue
            h = sha(raw)
            o.append(f'OBS {n} {meta(st2)} sha256={h} {"NAME_MATCH" if h == m.group(1) else "NAME_DIFF"}')
            check('obs', h == m.group(1), f'name_sha:{n}')
            found = found or (n == want and h == PIN['obs_sha'])
        check('obs', found, 'expected_missing')
    finally:
        os.close(fd)


def sec_proof():
    """seal/pb1trial2: попытка 1, proof.json с закреплённой SHA-256. Возвращает (proof, дескриптор попытки)."""
    o = OUT['proof']
    rfd, st = open_path(f'{SEAL}/{SERIES}')
    try:
        o.append(f'DIR {SEAL}/{SERIES} {meta(st)}')
        ents = sorted((show(n), kind(n, rfd)) for n in os.listdir(rfd))
        o.append('SERIES_ENTRIES ' + ','.join(f'{n}:{t}' for n, t in ents))
        if not check('proof', ents == [('1', 'dir')], 'attempts'):
            raise Stop('attempts')
        afd, st = open_dir('1', dir_fd=rfd)
    finally:
        os.close(rfd)
    try:
        o.append(f'ATTEMPT 1 {meta(st)}')
        check('proof', stat.S_IMODE(st.st_mode) == 0o700, 'attempt_mode')
        ents = sorted((show(n), kind(n, afd)) for n in os.listdir(afd))
        o.append('ATTEMPT_ENTRIES ' + ','.join(f'{n}:{t}' for n, t in ents))
        check('proof', ents == [('proof.json', 'file'), ('src', 'dir')], 'attempt_entries')
        raw, st = read_file('proof.json', afd, 256 * 1024)
        o.append(f'PROOF_FILE {meta(st)}')
        h = sha(raw)
        if not check('proof', h == PIN['proof_sha'], f'sha_diff {h}'):
            raise Stop('proof_sha')
        o.append(f'PROOF_SHA_MATCH {h}')
        obj = json.loads(raw.decode('ascii'))
        if not check('proof', isinstance(obj, dict) and set(obj) == FIELDS, 'fields'):
            raise Stop('proof_fields')
        lid = obj['lease_id']
        if not check('proof', isinstance(lid, str) and sha(lid.encode()) == PIN['lid_sha'], 'lid_sha'):
            raise Stop('lid_sha')
        o.append(f'LID_SHA_MATCH {PIN["lid_sha"]}')
        check('proof', obj['version'] == 1 and obj['series'] == SERIES, 'version_series')
        ck = obj['checks']
        check('proof', isinstance(ck, dict) and sorted(ck) == sorted(CHECKS)
              and all(isinstance(ck[k], dict) and ck[k].get('ok') is True for k in CHECKS), 'checks_h1_h10')
        toks = [OBS_TOKEN.findall(str(ck.get(k, {}).get('value', ''))) for k in ('H4', 'H5')]
        check('proof', toks == [[PIN['obs_sha']], [PIN['obs_sha']]], 'h4_h5_obs')
        src = obj['sources']
        check('proof', isinstance(src, list) and src and all(
            isinstance(s, dict) and set(s) == {'name', 'sha256', 'size'} and isinstance(s['name'], str)
            and NAME.fullmatch(s['name']) and isinstance(s['sha256'], str) and HEX64.fullmatch(s['sha256'])
            and type(s['size']) is int and s['size'] >= 0 for s in src), 'sources_shape')
        check('proof', isinstance(obj['inventory_sha256'], str) and HEX64.fullmatch(obj['inventory_sha256']),
              'inventory_field')
        view = {k: v for k, v in obj.items() if k != 'lease_id'}
        view['lease_id_sha256'] = PIN['lid_sha']
        o.append('PROOF ' + json.dumps(view, sort_keys=True, separators=(',', ':'), ensure_ascii=True))
        return obj, lid, afd
    except BaseException:
        os.close(afd)
        raise


def parse_inventory(raw):
    text = raw.decode('ascii')
    if not text.endswith('\n') or '\r' in text:
        raise Stop('inventory_eol')
    out, names = {}, []
    for ln in text[:-1].split('\n'):
        p = ln.split('  ')
        if len(p) != 7 or not HEX64.fullmatch(p[0]) or not p[1].isdigit() or str(int(p[1])) != p[1] \
                or not NAME.fullmatch(p[2]) or p[3] != f'phys={PRESERVE}/{p[2]}' or not p[4].startswith('orig=') \
                or not p[5].startswith('src=') or not MODE.fullmatch(p[5][4:]) or not p[6].startswith('orig_src='):
            raise Stop('inventory_line')
        orig, osrc = p[4][5:], p[6][9:]
        if not ((orig == '-' and osrc == '-' and p[2] == 'anchor.json')
                or (PATHRE.fullmatch(orig) and MODE.fullmatch(osrc))):
            raise Stop('inventory_orig')
        names.append(p[2])
        out[p[2]] = (p[0], int(p[1]))
    if names != sorted(set(names)):
        raise Stop('inventory_order')
    return out, text[:-1].split('\n')


def sec_src(obj, afd):
    o = OUT['src']
    sfd, st = open_dir('src', dir_fd=afd)
    try:
        o.append(f'DIR src {meta(st)}')
        check('src', stat.S_IMODE(st.st_mode) == 0o700, 'src_mode')
        inv_raw, st = read_file('INVENTORY.sha256', sfd)
        h = sha(inv_raw)
        o.append(f'INVENTORY {meta(st)} sha256={h}')
        if not check('src', h == obj['inventory_sha256'], 'inventory_sha'):
            raise Stop('inventory_sha')
        o.append('INVENTORY_SHA_MATCH proof.inventory_sha256')
        inv, lines = parse_inventory(inv_raw)
        for ln in lines:
            o.append('INV ' + ln)
        proof_map = {s['name']: (s['sha256'], s['size']) for s in obj['sources']}
        check('src', len(proof_map) == len(obj['sources']), 'sources_dup')
        check('src', inv == proof_map, 'inventory_vs_proof')
        ents = sorted((show(n), kind(n, sfd)) for n in os.listdir(sfd))
        want = sorted((n, 'file') for n in list(inv) + ['INVENTORY.sha256'])
        o.append(f'SRC_ENTRIES {len(ents)}')
        check('src', ents == want, 'src_set')
        for name in sorted(proof_map):
            try:
                data, st = read_file(name, sfd)
            except (Stop, OSError) as e:
                check('src', False, f'file:{name}:{type(e).__name__}')
                continue
            got = (sha(data), len(data))
            ok = got == proof_map[name] and got == inv.get(name)
            o.append(f'SRC {name} {meta(st)} sha256={got[0]} {"MATCH" if ok else "DIFF"}')
            check('src', ok, f'file:{name}')
    finally:
        os.close(sfd)


def sec_db():
    o = OUT['db']
    sql = ("SET default_transaction_read_only = on;\n"
           "SELECT 'RO ' || current_setting('transaction_read_only');\n"
           "SELECT 'ROWS_ALL ' || count(*) FROM bem_control.lease_seal;\n"
           "SELECT 'ROW ' || json_build_object('series', series, 'reason', reason, 'proof_sha256', proof_sha256, "
           "'sealed_at', sealed_at, 'sealed_by', sealed_by, 'lid_sha', "
           "encode(sha256(convert_to(lease_id::text, 'UTF8')), 'hex'))::text "
           f"FROM bem_control.lease_seal WHERE series = '{SERIES}' ORDER BY sealed_at;\n")
    p = subprocess.run(['/usr/sbin/runuser', '-u', 'postgres', '--', 'psql', '-X', '-A', '-t', '-q', '-v',
                        'ON_ERROR_STOP=1', '-d', 'bem'], input=sql.encode('ascii'), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=60, cwd='/', env={'PATH': os.environ.get('PATH', '')})
    lines = p.stdout.decode('ascii', 'replace').splitlines()
    o.extend(lines)
    o.append(f'RC psql = {p.returncode}')
    if p.returncode != 0:
        o.append('PSQL_ERR ' + p.stderr.decode('ascii', 'replace').replace('\n', ' ')[:200])
    check('db', p.returncode == 0, 'psql_rc')
    check('db', 'RO on' in lines, 'read_only')
    rows = [json.loads(x[4:]) for x in lines if x.startswith('ROW ')]
    check('db', len(rows) == 1, f'rows:{len(rows)}')
    if len(rows) == 1:
        r = rows[0]
        check('db', r.get('series') == SERIES and r.get('reason') == REASON, 'series_reason')
        check('db', r.get('proof_sha256') == PIN['proof_sha'], 'proof_sha')
        check('db', r.get('lid_sha') == PIN['lid_sha'], 'lid_sha')


def sec_r2_text(raw):
    """Строки R2_OUT (после совпадения SHA): ровно пять строк R2=, R2_OBS, R2_OBS_FILE, R2_OBS_CHECK, R2_DIAG."""
    o = OUT['r2_text']
    text = raw.decode('ascii')
    lines = text[:-1].split('\n') if text.endswith('\n') else None
    heads = ('R2=', 'R2_OBS ', 'R2_OBS_FILE ', 'R2_OBS_CHECK ', 'R2_DIAG ')
    if not check('r2_text', lines is not None and len(lines) == 5
                 and all(x.startswith(p) for x, p in zip(lines, heads)), 'lines'):
        return
    ps, ob = PIN['proof_sha'], PIN['obs_sha']
    check('r2_text', lines[0] == f'R2=SEALED_NOW status=SAFE_PRE_START k=1 sha={ps} failed=- reason=first', 'r2_line')
    check('r2_text', sha(lines[1][7:].encode('ascii')) == ob, 'obs_line_sha')
    check('r2_text', lines[2] == f'R2_OBS_FILE {OBS}/{SERIES}/obs-{ob}.json sha={ob}', 'obs_file_line')
    check('r2_text', lines[3] == f'R2_OBS_CHECK ok {ob}', 'obs_check_line')
    try:
        d = json.loads(lines[4][8:])
    except ValueError:
        d = None
    check('r2_text', isinstance(d, dict) and d.get('state') == 'PRIMARY_CHECKS', 'diag_state')
    check('r2_text', isinstance(d, dict) and d.get('ok') == {k: True for k in CHECKS}, 'diag_ok_h1_h10')
    check('r2_text', isinstance(d, dict) and d.get('obs_sha') == ob, 'diag_obs_sha')
    o.append('R2_TEXT_CHECKED 5 lines')


def run(sec, fn, *a):
    try:
        return fn(*a)
    except Stop as e:
        if not any(f.startswith(sec + ':') for f in FAIL):
            check(sec, False, str(e)[:120])
    except Exception as e:  # noqa: BLE001 — раздел не прошёл; остальные разделы идут дальше
        check(sec, False, f'{type(e).__name__}:{e}'[:120])
    return None


def main():
    if os.geteuid() != 0:
        print('REFUSED: run as root; nothing done')
        return 1
    raw = run('r2_out', sec_r2_out)
    run('obs', sec_obs)
    got = run('proof', sec_proof)
    lid = None
    if got:
        obj, lid, afd = got
        try:
            run('src', sec_src, obj, afd)
        finally:
            os.close(afd)
    else:
        check('src', False, 'proof_not_verified')
    run('db', sec_db)
    if raw is not None:
        run('r2_text', sec_r2_text, raw)
    else:
        check('r2_text', False, 'r2_out_not_verified')
    text = []
    for s in SECS:
        text.append(f'=== {s}')
        text.extend(OUT[s])
        if s == 'r2_out' and raw is not None:
            text.append('--- BEGIN R2_OUT')
            text.extend(raw.decode('ascii', 'backslashreplace').rstrip('\n').split('\n'))
            text.append('--- END R2_OUT')
        text.append(f'SEC {s} ' + ('FAIL' if any(f.startswith(s + ':') for f in FAIL) else 'PASS'))
    text.append('D17_FAIL ' + ','.join(FAIL) if FAIL else 'D17_OK')
    body = '\n'.join(text) + '\n'
    if lid and lid.lower() in body.lower():
        body = 'D17_FAIL lease_id_in_output\n'
    sys.stdout.buffer.write(body.encode('ascii', 'backslashreplace'))
    sys.stdout.flush()
    return 1 if FAIL or body.startswith('D17_FAIL lease') else 0


sys.exit(main())
