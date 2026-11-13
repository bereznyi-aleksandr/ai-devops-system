#!/usr/bin/python3
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_release.py
# ВЕРСИЯ: v0.7  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-13 11:21 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-13 17:11 +02:00
# ИСПОЛНИТЕЛЬ: Claude (чат «Завод 3.5.5 ПБ-1 · 04», сессия 70d36cf5)
# НАЗНАЧЕНИЕ: испытания выпуска 3.5.5 (zprobe_release.py v0.2, build_release_3_5_5.py v0.2) без сервера и без root —
#   положительные и отрицательные случаи по замечаниям ChatGPT REL1: C-01 (нет mv), M-01 (отказ до любой записи,
#   PARTIAL и продолжение), M-02 (тело функции с последним переводом строки), M-03 (строгие pins), M-04 (0/0, 184,
#   пропуск обязательного), M-05 (сбой журнала — FAIL, не WAIT), M-06 (ключи pins сборщика = проверки), M-07 (права,
#   владелец, предки), L-02 (уникальные имена). Установка испытывается в новой временной папке с подменой путей.
#   v0.2 (аудит ChatGPT REL2): T9–T11 (пропуск 40 и повтор 41, чужие имена), P6–P13 (типы полей посредника, rc
#   is-active), F1–F10 (обрыв EPERM/ENOSPC на каждом действии установки: под настоящим именем нет недоделанного,
#   повтор доходит до OK, заготовка остаётся), R1 (renameat2 не заменяет), L1–L2 (список объектов папки пакета).
#   v0.3 (аудит ChatGPT REL3): R1 и заготовки убраны (переименования нет); F1–F10 — обрыв на каждом действии
#   (useradd, mkdir, chown, chmod, open, write, fchown, fchmod, fsync): повтор достраивает по дневнику и доходит до OK;
#   U1–U2 (useradd оборвался после группы; группа без дневника), W1–W6 (достройка только своего недоделанного по
#   INTENT, чужое — CONFLICT), C2 (в коде выпуска нет вызовов переименования и удаления), P15–P23 (peer — IPv4 петли).
#   v0.4 (аудит ChatGPT REL4 M-01): F1–F12 (обрыв и на groupadd; обрыв до записи CREATED — повтор REFUSED, объект не
#   тронут), U1–U3 (группа своя только по CREATED с gid), W1–W10 (достройка только при INTENT+CREATED с тем же inode
#   и без DONE: завершённое (A), INTENT без CREATED (B), другой inode — REFUSED), X1 (второй install одновременно —
#   REFUSED, ничего не создано).
#   v0.5 (аудит ChatGPT REL5 M-01): S1–S4 — подмена между планом и действием (на шаге reopen): чужой файл с теми же
#   байтами и другим inode, свой файл с изменённым началом, чужой пустой каталог, свой каталог, в котором появился
#   файл — отказ, ни записи, ни смены владельца и прав. Подмену делает только испытание в своей временной папке.
#   v0.6 (check на сервере zavod-1 2026-11-13): PR1–PR8 — строки READY и BUSY посредника; N1–N3 — цепочка egress_closed
#   в том виде, как её печатает nftables v1.0.9 (без «level warn»).
#   v0.7 (аудит ChatGPT REL7B): строки READY и BUSY с полем at; PR9–PR23 — сломанная строка посредника, повтор ключа,
#   плохой allow, at; N4–N8 — лишняя или пропавшая цепочка таблицы, перестановка правил.
# ВЫЗОВ: python3 -I -B test_zprobe_release.py  (Linux; на Windows части с правами Unix — SKIP). Итог:
#   ZPROBE_RELEASE_TESTS N/N PASS. Запускается в CI zavod-probes-3-5-5 на x64 и Arm64.
# ОГРАНИЧЕНИЯ: пишет только в новую временную папку (tempfile.mkdtemp или ZPROBE_TEST_ROOT); ничего не удаляет.
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import types

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
UNIX = hasattr(os, 'getuid')
if not UNIX:   # Windows: модулей pwd/grp нет — заглушки только для чистых функций
    for _m in ('pwd', 'grp', 'fcntl'):
        sys.modules[_m] = types.ModuleType(_m)
sys.path.insert(0, HERE)
import zprobe_release as Z  # noqa: E402
import build_release_3_5_5 as B  # noqa: E402

RESULTS = []


def case(name, ok, detail=''):
    RESULTS.append(bool(ok))
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else ' -> ' + str(detail)), flush=True)


def skip(name):
    print('SKIP ' + name)


def quiet(fn, *a):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*a)
    return rc, buf.getvalue()


def tmp():
    root = os.environ.get('ZPROBE_TEST_ROOT') or None
    return tempfile.mkdtemp(prefix='zrel-', dir=root)


# ---------- M-02: тело функции ----------
def t_sql():
    with open(os.path.join(REPO, 'zavod', 'kernel', 'db', '06_zavod_ext_04.sql'), 'rb') as f:
        body = Z.sql_body(f.read(), 'lease_reserve_start')
    case('S1 body found and ends with a line feed', body is not None and body.endswith(b'\n'))
    case('S2 database text equal to the file (hex + psql line feed) -> same', Z.prosrc_same(0, body.hex() + '\n', body))
    case('S3 database text with an extra line feed -> differs', not Z.prosrc_same(0, (body + b'\n').hex() + '\n', body))
    case('S4 database text without the last line feed -> differs', not Z.prosrc_same(0, body[:-1].hex() + '\n', body))
    alt = bytearray(body)
    alt[len(alt) // 2] ^= 1
    case('S5 one byte changed -> differs', not Z.prosrc_same(0, bytes(alt).hex() + '\n', body))
    case('S6 psql rc=1 -> differs', not Z.prosrc_same(1, body.hex() + '\n', body))
    case('S7 not hex -> differs', not Z.prosrc_same(0, 'zz\n', body))
    case('S8 empty answer -> differs', not Z.prosrc_same(0, '', body))
    case('S9 no body in file -> differs', not Z.prosrc_same(0, '00\n', None))


# ---------- M-04: испытания ----------
def tests_out(n=185, last=None, mutate=None):
    lines = []
    for i in range(1, n + 1):
        nm = f'{i} case'
        if i in (174, 175):
            nm += ' (SKIPPED: not Windows)'
        lines.append(f'PASS {nm} -> None')
    lines.insert(0, Z.ALLOWED_SKIP + ' — counted as PASS only on this platform')
    if mutate:
        mutate(lines)
    lines.append(last or f'ZPROBE_TESTS {n}/{n} PASS')
    return '\n'.join(lines) + '\n'


def fake_names_sha(n=185):
    ns = [f'{i} case' + (' (SKIPPED: not Windows)' if i in (174, 175) else '') for i in range(1, n + 1)]
    return Z.sha_b(('\n'.join(sorted(ns)) + '\n').encode('utf-8'))


def t_tests():
    real_pin = Z.EXPECTED_TEST_NAMES_SHA256
    case('T0 pinned list of test names is a SHA-256', len(real_pin) == 64 and all(c in '0123456789abcdef' for c in real_pin))
    case('T11 fake names against the real pin -> FAIL', Z.tests_verdict(0, tests_out())[0] == 'FAIL')
    Z.EXPECTED_TEST_NAMES_SHA256 = fake_names_sha()
    case('T1 185/185, 174-175 skipped on Linux -> OK', Z.tests_verdict(0, tests_out())[0] == 'OK')
    case('T2 0/0 PASS -> FAIL', Z.tests_verdict(0, 'ZPROBE_TESTS 0/0 PASS\n')[0] == 'FAIL')
    case('T3 184/184 -> FAIL', Z.tests_verdict(0, tests_out(184))[0] == 'FAIL')
    case('T4 rc=1 -> FAIL', Z.tests_verdict(1, tests_out())[0] == 'FAIL')

    def sk142(ls):
        ls[142] = 'PASS 142 R7 live relay (SKIPPED: not Linux) -> None'
    case('T5 required 142 skipped -> FAIL', Z.tests_verdict(0, tests_out(mutate=sk142))[0] == 'FAIL')

    def extra_skip(ls):
        ls.insert(1, 'SKIP 163 body (symlink not allowed here)')
    case('T6 unexpected SKIP line -> FAIL', Z.tests_verdict(0, tests_out(mutate=extra_skip))[0] == 'FAIL')

    def a_fail(ls):
        ls[10] = 'FAIL 10 case -> x'
    case('T7 a FAIL line -> FAIL', Z.tests_verdict(0, tests_out(mutate=a_fail))[0] == 'FAIL')
    case('T8 last line says 186/186 -> FAIL', Z.tests_verdict(0, tests_out(last='ZPROBE_TESTS 186/186 PASS'))[0] == 'FAIL')

    def drop40_dup41(ls):    # REL2 N03: 185 строк PASS, случая 40 нет, 41 дважды
        i40 = next(i for i, x in enumerate(ls) if x.startswith('PASS 40 '))
        i41 = next(i for i, x in enumerate(ls) if x.startswith('PASS 41 '))
        ls[i40] = ls[i41]
    v = Z.tests_verdict(0, tests_out(mutate=drop40_dup41))
    case('T9 REL2 M-03 case 40 missing, 41 repeated (185 lines) -> FAIL', v[0] == 'FAIL' and 'duplicate_names=1' in v[1], v)

    def rename40(ls):
        i40 = next(i for i, x in enumerate(ls) if x.startswith('PASS 40 '))
        ls[i40] = 'PASS 40 other check -> None'
    case('T10 one test name differs from the pinned list -> FAIL', Z.tests_verdict(0, tests_out(mutate=rename40))[0] == 'FAIL')
    Z.EXPECTED_TEST_NAMES_SHA256 = real_pin


# ---------- M-05: журнал ядра и посредника ----------
def t_journal():
    probe = '{"MESSAGE":"x","__REALTIME_TIMESTAMP":"1"}\n'
    srv = ('table inet zavod {\n\tchain egress_closed {\n\t\tcounter packets 12 bytes 720 log prefix "zavod-egress-refused "\n'
           '\t\tmeta l4proto tcp reject with tcp reset\n\t\treject with icmpx admin-prohibited\n\t}\n}\n')
    case('N1 CHECK-2 egress_closed as nft v1.0.9 prints it (no "level warn") == NFT_EXPECTED',
         Z.R._nft_chains(srv).get('egress_closed') == Z.R.NFT_EXPECTED['egress_closed'])
    case('N2 CHECK-2 other level printed -> differs',
         Z.R._nft_chains(srv.replace('refused "\n', 'refused " level info\n')).get('egress_closed')
         != Z.R.NFT_EXPECTED['egress_closed'])
    exp = Z.R.NFT_EXPECTED
    tbl = ('table inet zavod {\n'
           + ''.join('\tchain %s {\n%s\t}\n' % (n, ''.join('\t\t%s\n' % ln for ln in exp[n])) for n in ('egress_closed', 'output'))
           + '\tchain input {\n\t\ttcp dport 22 accept\n\t}\n}\n')
    case('N4 REL7 M-03 table with exactly egress_closed, input, output -> no problem', Z.R.nft_problem(tbl) is None)
    case('N5 REL7 M-03 third regular chain "bypass" -> nft_chain_set',
         Z.R.nft_problem(tbl.replace('\tchain input {', '\tchain bypass {\n\t\taccept\n\t}\n\tchain input {')) == 'nft_chain_set')
    case('N6 REL7 M-03 extra base chain (hook) -> nft_chain_set',
         Z.R.nft_problem(tbl.replace('\tchain input {', '\tchain pre {\n\t\ttype filter hook prerouting priority 0; '
                                     'policy accept;\n\t}\n\tchain input {')) == 'nft_chain_set')
    case('N7 REL7 M-03 input chain missing -> nft_chain_set',
         Z.R.nft_problem(tbl.replace('\tchain input {\n\t\ttcp dport 22 accept\n\t}\n', '')) == 'nft_chain_set')
    case('N8 REL7 rules swapped in egress_closed -> differs',
         Z.R.nft_problem(tbl.replace('\t\tmeta l4proto tcp reject with tcp reset\n\t\treject with icmpx admin-prohibited\n',
                                     '\t\treject with icmpx admin-prohibited\n\t\tmeta l4proto tcp reject with tcp reset\n'))
         == 'nft_chain_differs_egress_closed')
    case('N3 CHECK-2 missing reject line -> differs',
         Z.R._nft_chains(srv.replace('\t\treject with icmpx admin-prohibited\n', '')).get('egress_closed')
         != Z.R.NFT_EXPECTED['egress_closed'])
    case('J1 journalctl rc=1 -> FAIL, not WAIT', Z.kernel_verdict(1, '', 'no access', 0, probe)[0] == 'FAIL')
    case('J2 read OK, no refused lines -> WAIT', Z.kernel_verdict(0, probe, '', 0, probe)[0] == 'WAIT')
    case('J3 kernel journal empty (probe has no line) -> FAIL', Z.kernel_verdict(0, '', '', 0, '')[0] == 'FAIL')
    case('J4 probe rc=1 -> FAIL', Z.kernel_verdict(0, '', '', 1, probe)[0] == 'FAIL')
    case('J5 a line is not JSON -> FAIL', Z.kernel_verdict(0, 'garbage\n', '', 0, probe)[0] == 'FAIL')
    case('P1 proxy inactive -> FAIL', Z.proxy_verdict('inactive', 0, '')[0] == 'FAIL')
    case('P2 proxy journal rc=1 -> FAIL, not WAIT', Z.proxy_verdict('active', 1, '')[0] == 'FAIL')
    case('P3 active, read OK, no records -> WAIT', Z.proxy_verdict('active', 0, 'other\n')[0] == 'WAIT')
    case('P4 broken record -> FAIL', Z.proxy_verdict('active', 0, 'ZAVOD_PROXY {bad\n')[0] == 'FAIL')
    good = 'ZAVOD_PROXY {"cgroup": 5, "peer": "127.0.0.1:4000", "uid": 61200}\n'
    case('P5 full record -> OK', Z.proxy_verdict('active', 0, good)[0] == 'OK')
    case('P6 REL2 uid not a number -> FAIL', Z.proxy_verdict('active', 0, good.replace('61200', '"x"'))[0] == 'FAIL')
    for name, cg in (('P7 cgroup "bad"', '"bad"'), ('P8 cgroup -1', '-1'), ('P9 cgroup false', 'false'),
                     ('P10 cgroup 0', '0')):
        case(f'{name} -> FAIL (REL2 N02)', Z.proxy_verdict('active', 0, good.replace('"cgroup": 5', f'"cgroup": {cg}'))[0] == 'FAIL')
    case('P11 cgroup null only (peer socket not found) -> WAIT, not OK',
         Z.proxy_verdict('active', 0, good.replace('"cgroup": 5', '"cgroup": null'))[0] == 'WAIT')
    case('P12 systemctl is-active rc=3 -> FAIL', Z.proxy_verdict('active', 0, good, 3)[0] == 'FAIL')
    case('P13 peer port 70000 -> FAIL', Z.proxy_verdict('active', 0, good.replace(':4000', ':70000'))[0] == 'FAIL')
    case('P14 uid true -> FAIL', Z.proxy_verdict('active', 0, good.replace('61200', 'true'))[0] == 'FAIL')
    # REL7: строки как их пишет cell/zavod-proxy log(): json.dumps(sort_keys=True) и поле at.
    ready = ('ZAVOD_PROXY {"allow": ["files.pythonhosted.org", "pypi.org"], "at": "2026-11-13T14:38:02Z", '
             '"decision": "READY", "listen": "127.0.0.2:3128"}\n')
    busy = 'ZAVOD_PROXY {"at": "2026-11-13T14:38:03Z", "decision": "BUSY", "peer": "127.0.0.1:4001"}\n'
    case('PR1 CHECK-1 service READY line then full record -> OK (server 2026-11-13: was bad peer None)',
         Z.proxy_verdict('active', 0, ready + good)[0] == 'OK')
    case('PR2 CHECK-1 only READY line -> WAIT', Z.proxy_verdict('active', 0, ready)[0] == 'WAIT')
    case('PR3 CHECK-1 READY with extra field -> FAIL',
         Z.proxy_verdict('active', 0, ready.replace('"decision"', '"peer": "x", "decision"'))[0] == 'FAIL')
    case('PR4 CHECK-1 READY on other listen address -> FAIL',
         Z.proxy_verdict('active', 0, ready.replace('127.0.0.2:3128', '0.0.0.0:3128'))[0] == 'FAIL')
    case('PR5 CHECK-1 BUSY line + READY only -> WAIT (BUSY is not a full record)',
         Z.proxy_verdict('active', 0, ready + busy)[0] == 'WAIT')
    case('PR6 CHECK-1 BUSY with bad peer -> FAIL',
         Z.proxy_verdict('active', 0, busy.replace('127.0.0.1:4001', '10.0.0.1:4001'))[0] == 'FAIL')
    case('PR7 CHECK-1 BUSY with uid field -> FAIL',
         Z.proxy_verdict('active', 0, busy.replace('"decision"', '"uid": 1, "decision"'))[0] == 'FAIL')
    names = '["files.pythonhosted.org", "pypi.org"]'
    pr_bad = (
        ('PR9 REL7 M-01 broken proxy line after a full record', good + 'ZAVOD_PROXY NOT_JSON\n'),
        ('PR10 REL7 M-01 proxy line with a JSON array', good + 'ZAVOD_PROXY []\n'),
        ('PR11 REL7 M-01 proxy line with two spaces', good + 'ZAVOD_PROXY  {"peer": "127.0.0.1:1"}\n'),
        ('PR12 REL7 M-01 proxy line with bad JSON', good + 'ZAVOD_PROXY {"peer": \n'),
        ('PR13 REL7 M-01 proxy error line (refuse to run as root)', good + 'ZAVOD_PROXY refuse to run as root\n'),
        ('PR14 REL7 M-02 READY with two listen keys',
         ready.replace('"listen"', '"listen": "0.0.0.0:3128", "listen"') + good),
        ('PR15 REL7 M-02 READY allow with null, number, star', ready.replace(names, '[null, 23, "*"]') + good),
        ('PR16 REL7 M-02 READY allow not sorted', ready.replace(names, '["pypi.org", "files.pythonhosted.org"]') + good),
        ('PR17 REL7 M-02 READY allow repeats a name', ready.replace(names, '["pypi.org", "pypi.org"]') + good),
        ('PR18 REL7 M-02 READY allow has a GitHub name',
         ready.replace(names, '["pypi.org", "raw.githubusercontent.com"]') + good),
        ('PR19 REL7 READY without at', ready.replace('"at": "2026-11-13T14:38:02Z", ', '') + good),
        ('PR20 REL7 BUSY with bad at', busy.replace('2026-11-13T14:38:03Z', 'yesterday') + good),
        ('PR21 REL7 M-02 connection record repeats peer',
         'ZAVOD_PROXY {"cgroup": 5, "peer": "10.0.0.1:1", "peer": "127.0.0.1:4000", "uid": 61200}\n'))
    for name, text in pr_bad:
        case(name + ' -> FAIL', Z.proxy_verdict('active', 0, text)[0] == 'FAIL')
    case('PR22 REL7 READY with empty allow (proxy refuses all) + full record -> OK',
         Z.proxy_verdict('active', 0, ready.replace(names, '[]') + good)[0] == 'OK')
    case('PR23 REL7 foreign journal line (not ZAVOD_PROXY) is skipped -> OK',
         Z.proxy_verdict('active', 0, 'Started zavod-proxy.service\n' + ready + good)[0] == 'OK')
    case('PR8 CHECK-1 other decision without peer -> FAIL',
         Z.proxy_verdict('active', 0, 'ZAVOD_PROXY {"decision": "STOP"}\n')[0] == 'FAIL')
    n = 15
    for bad in ('NOT_AN_IP:40000', 'https://x:40000', 'hostname:40000', '[::1]:40000', '10.0.0.1:4000',
                '127.0.0.01:4000', '127.0.0.1:04000', '127.0.0.1:0'):
        case(f'P{n} REL3 peer {bad} -> FAIL', Z.proxy_verdict('active', 0, good.replace('127.0.0.1:4000', bad))[0] == 'FAIL')
        n += 1
    case(f'P{n} REL3 peer 127.0.0.3:49998 (loopback IPv4) -> OK',
         Z.proxy_verdict('active', 0, good.replace('127.0.0.1:4000', '127.0.0.3:49998'))[0] == 'OK')


# ---------- M-03 и M-06: pins и сборщик ----------
def t_pins_and_builder():
    case('K1 builder PIN_KEYS = check PIN_FILES (keys and files)',
         {k: p for k, p in B.PIN_KEYS} == {k: 'zavod/ops/' + p for k, p in Z.PIN_FILES.items()})
    head = subprocess.run(['git', '-C', REPO, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    pins, tar, sh_b = B.build(REPO, head)
    pins2, tar2, sh2 = B.build(REPO, head)
    case('K2 build is deterministic', (pins, tar, sh_b) == (pins2, tar2, sh2))
    d = tmp()
    good = os.path.join(d, 'pins_good.txt')
    with open(good, 'xb') as f:
        f.write(pins)
    p, errs = Z.read_pins(good)
    case('K3 built pins: 16 keys, no errors', not errs and len(p) == 16, errs)
    lines = pins.decode().split('\n')

    def variant(name, new_lines):
        path = os.path.join(d, name)
        with open(path, 'xb') as f:
            f.write('\n'.join(new_lines).encode())
        return Z.read_pins(path)[1]
    e = variant('miss.txt', [ln for ln in lines if not ln.startswith('zagent@.service ')])
    case('K4 pin zagent@.service missing -> error', any('missing key zagent@.service' in x for x in e), e)
    e = variant('dup.txt', lines + [next(ln for ln in lines if ln.startswith('zavod-gate '))])
    case('K5 repeated key -> error', any('repeated key zavod-gate' in x for x in e), e)
    e = variant('extra.txt', lines + ['extra_key ' + '0' * 64])
    case('K6 unknown key -> error', any('unknown key extra_key' in x for x in e), e)
    e = variant('hex.txt', [('zavod-proxy XYZ' if ln.startswith('zavod-proxy ') else ln) for ln in lines])
    case('K7 bad value -> error', any('bad value for zavod-proxy' in x for x in e), e)
    e = variant('three.txt', [(ln + ' x' if ln.startswith('zavod-proxy ') else ln) for ln in lines])
    case('K8 three fields -> error', any('is not "key value"' in x for x in e), e)
    text = sh_b.split(b'\n__ZPROBE_PKG_BASE64__\n')[0].decode()
    with open(os.path.join(HERE, 'operator_command_3_5_5.txt'), encoding='utf-8') as f:
        cmd = f.read().rstrip('\n').split('\n')[-1]
    import re
    case('C1 release file and operator command have no mv (no rename or move)',
         not re.search(r'(^|[\s;|&(){}])mv\s', text) and not re.search(r'(^|[\s;|&(){}])mv\s', cmd))
    case('C2 operator command writes a new file only (noclobber)', 'noclobber' in cmd and '-o "$F"' not in cmd)
    shp = os.path.join(d, 'rel.sh')
    with open(shp, 'xb') as f:
        f.write(sh_b)
    r = subprocess.run(['bash', '-n', shp], capture_output=True, text=True)
    case('C3 bash -n of the release file', r.returncode == 0, r.stderr)
    if UNIX and os.geteuid() != 0:
        r = subprocess.run(['bash', shp, 'check'], capture_output=True, text=True)
        case('C4 not root -> REFUSED before anything', r.returncode == 2 and 'REFUSED: run as root' in r.stdout, r.stdout)
    else:
        skip('C4 (needs a non-root Unix user)')
    import tarfile
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        names = [m.name for m in t.getmembers() if m.isfile()]
        man = t.extractfile('MANIFEST.sha256').read().decode()
    case('C5 inventory: every file except MANIFEST listed once; NF in the release file',
         sorted(ln.split('  ', 1)[1] for ln in man.splitlines()) == sorted(n for n in names if n != 'MANIFEST.sha256')
         and f'NF={len(names)}\n' in text)
    case('L0 release file compares the full listing (LISTING_CMD, LS)',
         B.LISTING_CMD.replace('\\n', '\\n') in text and re.search(r'\nLS=[0-9a-f]{64}\n', text) is not None)
    if UNIX:
        ls = re.search(r'\nLS=([0-9a-f]{64})\n', text).group(1)
        old = os.umask(0o022)
        try:
            pd = os.path.join(tmp(), 'pkg')
            os.mkdir(pd, 0o755)
            r = subprocess.run(['tar', '-C', pd, '--no-same-owner', '-xf', '-'], input=tar, capture_output=True)
            got = subprocess.run(['bash', '-c', B.LISTING_CMD], cwd=pd, capture_output=True, text=True).stdout.strip()
            case('L1 GNU tar unpack: listing equals LS', r.returncode == 0 and got == ls, (got, ls))
            os.mkdir(os.path.join(pd, 'EXTRA_EMPTY_DIRECTORY_NOT_IN_MANIFEST'), 0o755)
            got = subprocess.run(['bash', '-c', B.LISTING_CMD], cwd=pd, capture_output=True, text=True).stdout.strip()
            case('L2 REL2 N04 extra empty folder -> listing differs', got != ls, got)
        finally:
            os.umask(old)
    else:
        skip('L1-L2 (GNU tar and find)')


# ---------- M-01, M-07, L-02: установка в новой временной папке ----------
class Env:
    def __init__(self, pkg=None):
        self.base = tmp()
        os.chmod(self.base, 0o755)
        for d in ('usr/local/lib/zavod', 'var/lib/zavod', 'etc/systemd/system'):
            os.makedirs(os.path.join(self.base, d), mode=0o755)
        for d in ('usr', 'usr/local', 'usr/local/lib', 'usr/local/lib/zavod', 'var', 'var/lib', 'var/lib/zavod',
                  'etc', 'etc/systemd', 'etc/systemd/system'):
            os.chmod(os.path.join(self.base, d), 0o755)
        self.pkg = pkg or REPO
        self.user = None
        self.user_ok = True
        self.group = None
        self.useradd_crash = False     # REL3: useradd создал группу и оборвался
        self.calls = []
        self.argv = []
        Z.TRUST_FROM = self.base
        Z.LIB = os.path.join(self.base, 'usr/local/lib/zavod/probes')
        Z.DATA = os.path.join(self.base, 'var/lib/zavod/probes')
        Z.UNIT = os.path.join(self.base, 'etc/systemd/system/zprobe-run@.service')
        Z.JOURNAL_DIR = os.path.join(self.base, 'root')
        os.mkdir(Z.JOURNAL_DIR, 0o700)
        Z.ROOT_UID, Z.ROOT_GID = os.getuid(), os.getgid()
        Z.get_user = self.get_user
        Z.get_group = self.get_group
        Z.sh = self.sh
        Z.FAULT = None

    def get_user(self, name):
        if name == 'zprobe' and self.user and self.user_ok:
            return self.user
        return None

    def get_group(self, name):
        return self.group if name == 'zprobe' else None

    def sh(self, *args, **kw):
        self.calls.append(args[0])
        self.argv.append(args)
        if args[0] == 'useradd':
            if self.useradd_crash:
                self.useradd_crash = False
                return 1, '', 'useradd: interrupted'
            self.user = types.SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_shell='/usr/sbin/nologin')
            return 0, '', ''
        if args[0] == 'groupadd':
            self.group = types.SimpleNamespace(gr_gid=999, gr_mem=[])
            return 0, '', ''
        if args[0] == 'systemctl' and 'show' in args:
            return 0, f'ReadWritePaths={Z.DATA}\nUser=zprobe\n', ''
        return 0, '', ''

    def created(self):
        return sorted(os.path.relpath(os.path.join(r, n), self.base) for r, ds, fs in os.walk(self.base) for n in ds + fs)


def commit():
    return 'a' * 40


def t_install():
    if not UNIX:
        skip('I1-I9 install (needs Unix owners and modes)')
        return
    Z.SYSTEM_UID_MAX = 10 ** 9
    e = Env()
    with open(Z.UNIT, 'xb') as f:
        f.write(b'[Unit]\nDescription=foreign\n')
    before = e.created()
    rc, out = quiet(Z.install, e.pkg, commit())
    case('I1 M-01 foreign unit -> REFUSED before any change (no files, no folders, no user)',
         rc == 1 and 'REFUSED' in out and e.created() == before and 'useradd' not in e.calls, out)

    e = Env()
    rc, out = quiet(Z.install, e.pkg, commit())
    lib_ok = all(oct(os.stat(os.path.join(Z.LIB, n)).st_mode & 0o7777) == oct(m) for n, m in Z.LIB_FILES.items())
    case('I2 clean install -> OK, modes as planned', rc == 0 and 'ZPROBE_355_INSTALL=OK' in out and lib_ok, out)
    rc, out = quiet(Z.install, e.pkg, commit())
    case('I3 repeat -> ALREADY, nothing new', rc == 0 and 'ZPROBE_355_INSTALL=ALREADY' in out, out)

    e = Env()
    os.mkdir(Z.LIB)
    os.chmod(Z.LIB, 0o777)
    rc, out = quiet(Z.install, e.pkg, commit())
    case('I4 M-07 program folder writable by others -> REFUSED, data folder not created',
         rc == 1 and 'REFUSED' in out and not os.path.exists(Z.DATA), out)

    e = Env()
    rc, out = quiet(Z.install, e.pkg, commit())
    os.chmod(os.path.join(Z.LIB, 'zprobe_rules.py'), 0o666)
    rc, out = quiet(Z.install, e.pkg, commit())
    case('I5 M-07 same bytes but mode 0666 -> REFUSED', rc == 1 and 'REFUSED' in out and 'zprobe_rules.py' in out, out)

    e = Env()
    os.chmod(os.path.join(e.base, 'etc'), 0o775)
    rc, out = quiet(Z.install, e.pkg, commit())
    case('I6 M-07 ancestor folder writable by group -> REFUSED, nothing created',
         rc == 1 and 'REFUSED' in out and not os.path.exists(Z.LIB), out)

    e = Env()
    e.user_ok = False          # useradd «прошёл», но учётной записи нет — сбой посреди второго прохода
    rc, out = quiet(Z.install, e.pkg, commit())
    case('I7 M-01 failure in the middle -> PARTIAL with the list of what was created',
         rc == 1 and 'ZPROBE_355_INSTALL=PARTIAL' in out and Z.LIB in out and not os.path.exists(Z.DATA), out)
    e.user_ok = True
    rc, out = quiet(Z.install, e.pkg, commit())
    case('I8 repeat after PARTIAL continues -> OK', rc == 0 and 'ZPROBE_355_INSTALL=OK' in out, out)

    pk = tmp()
    for n in list(Z.LIB_FILES) + ['zprobe-run@.service']:
        src = os.path.join(REPO, 'zavod', 'ops', 'server', 'probes', n)
        dst = os.path.join(pk, 'zavod', 'ops', 'server', 'probes', n)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(src, 'rb') as f:
            b = f.read()
        if n == 'zprobe-run@.service':
            b = b.replace(b'\nReadWritePaths=/var/lib/zavod/probes\n', b'\n')
        with open(dst, 'xb') as f:
            f.write(b)
    e = Env(pkg=pk)
    rc, out = quiet(Z.install, e.pkg, commit())
    case('I9 package unit without ReadWritePaths -> REFUSED before any change',
         rc == 1 and 'package unit has no line ReadWritePaths' in out and not os.path.exists(Z.LIB), out)

    e = Env()
    e.user = types.SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_shell='/bin/bash')
    rc, out = quiet(Z.install, e.pkg, commit())
    case('I10 user zprobe with a login shell -> REFUSED', rc == 1 and 'not a system nologin account' in out, out)


def journals():
    return [os.path.join(Z.JOURNAL_DIR, n) for n in sorted(os.listdir(Z.JOURNAL_DIR))]


def intent_line(**d):
    import json
    return ('INTENT ' + json.dumps(d, sort_keys=True) + '\n').encode()


def write_journal(*records):
    import json
    with open(os.path.join(Z.JOURNAL_DIR, Z.JOURNAL_PREFIX + '20261113T000000Z-01.journal'), 'xb') as f:
        for kind, d in records:
            f.write((kind + ' ' + json.dumps(d, sort_keys=True) + '\n').encode())


def ident(path):
    st = os.lstat(path)
    return {'path': path, 'dev': st.st_dev, 'ino': st.st_ino}


def t_faults():
    """REL3 C-01, REL4 M-01: обрыв на каждом действии прохода 2 — повтор install достраивает только объект, который
    сам создал (INTENT, CREATED с тем же inode, без DONE), и доходит до OK; ничего не удалено и не переименовано;
    всё остальное — CONFLICT, объект не тронут."""
    if not UNIX:
        skip('F1-F12, U1-U3, W1-W10, X1 (Unix owners, flock)')
        return
    import errno
    import fcntl
    rules = lambda: os.path.join(Z.LIB, 'zprobe_rules.py')  # noqa: E731
    data = open(os.path.join(REPO, 'zavod/ops/server/probes/zprobe_rules.py'), 'rb').read()
    n = 1
    for step, err, tgt in (('groupadd', errno.EPERM, 'group'), ('useradd', errno.EPERM, 'user'),
                           ('mkdir', errno.EPERM, 'data'), ('chown', errno.EPERM, 'data'),
                           ('chmod', errno.EPERM, 'data'), ('open', errno.ENOSPC, 'file'), ('write', errno.ENOSPC, 'file'),
                           ('fchown', errno.EPERM, 'file'), ('fchmod', errno.EPERM, 'file'), ('fsync', errno.EIO, 'file')):
        e = Env()
        target = {'group': 'group:zprobe', 'user': 'user:zprobe', 'data': Z.DATA, 'file': rules()}[tgt]
        hit = []

        def fault(s, p, step=step, err=err, target=target, hit=hit):
            if s == step and p == target and not hit:
                hit.append(p)
                raise OSError(err, os.strerror(err), p)
        Z.FAULT = fault
        rc1, out1 = quiet(Z.install, e.pkg, commit())
        Z.FAULT = None
        acts, probs = Z.plan(e.pkg, commit())
        js = journals()
        rc2, out2 = quiet(Z.install, e.pkg, commit())
        st = Z.state_file(rules(), data, 0o644, Z.ROOT_UID, Z.ROOT_GID)
        case(f'F{n} {step} fails ({errno.errorcode[err]}) on {os.path.basename(target)}: PARTIAL with journal, '
             'plan has no conflicts, repeat finishes -> OK, nothing removed',
             hit and rc1 == 1 and 'ZPROBE_355_INSTALL=PARTIAL' in out1 and 'journal=' in out1 and not probs and js
             and rc2 == 0 and 'ZPROBE_355_INSTALL=OK' in out2 and st == 'same' and e.calls.count('groupadd') == 1
             and all(os.path.lexists(x) for x in js), (out1, probs, out2, st))
        n += 1
    for tgt in ('data', 'file'):
        e = Env()
        target = Z.DATA if tgt == 'data' else rules()
        hit = []

        def fault(s, p, target=target, hit=hit):
            if s == 'record' and p == target and not hit:
                hit.append(p)
                raise OSError(errno.EIO, 'stop before CREATED', p)
        Z.FAULT = fault
        rc1, out1 = quiet(Z.install, e.pkg, commit())
        Z.FAULT = None
        before = e.created()
        rc2, out2 = quiet(Z.install, e.pkg, commit())
        case(f'F{n} REL4 stop after {"mkdir" if tgt == "data" else "O_EXCL"} but before CREATED: repeat -> REFUSED, '
             'object not touched (no proof it is ours)',
             hit and rc1 == 1 and 'PARTIAL' in out1 and rc2 == 1 and 'REFUSED' in out2 and e.created() == before
             and os.path.lexists(target), (out1, out2))
        n += 1
    e = Env()
    rc, out = quiet(Z.install, e.pkg, commit())
    rc3, out3 = quiet(Z.install, e.pkg, commit())
    case(f'F{n} clean install: one journal; repeat ALREADY writes no new journal',
         rc == 0 and rc3 == 0 and 'ALREADY' in out3 and len(journals()) == 1, (out, out3, journals()))

    e = Env()
    e.useradd_crash = True
    rc1, out1 = quiet(Z.install, e.pkg, commit())
    acts, probs = Z.plan(e.pkg, commit())
    rc2, out2 = quiet(Z.install, e.pkg, commit())
    case('U1 useradd fails after own groupadd -> PARTIAL; repeat: own group (CREATED gid) -> useradd --gid -> OK',
         rc1 == 1 and 'PARTIAL' in out1 and acts and acts[0] == ('user', 'zprobe') and not probs and rc2 == 0
         and 'ZPROBE_355_INSTALL=OK' in out2 and e.calls.count('groupadd') == 1
         and all('--gid' in a for a in e.argv if a[0] == 'useradd'), (out1, acts, probs, out2))
    e = Env()
    e.group = types.SimpleNamespace(gr_gid=999, gr_mem=[])
    rc, out = quiet(Z.install, e.pkg, commit())
    case('U2 group zprobe without user and without journal -> REFUSED, nothing created',
         rc == 1 and 'REFUSED' in out and not os.path.lexists(Z.LIB) and 'useradd' not in e.calls, out)
    e = Env()
    e.group = types.SimpleNamespace(gr_gid=999, gr_mem=[])
    write_journal(('INTENT', {'kind': 'group', 'path': 'group:zprobe'}))
    rc, out = quiet(Z.install, e.pkg, commit())
    case('U3 REL4 group with INTENT but no CREATED gid -> REFUSED', rc == 1 and 'REFUSED' in out
         and 'useradd' not in e.calls, out)

    it = dict(kind='file', sha=Z.sha_b(data), size=len(data), mode=0o644)

    def half_made(body, how):
        e = Env()
        e.user = types.SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_shell='/usr/sbin/nologin')
        os.mkdir(Z.LIB, 0o755)
        os.chmod(Z.LIB, 0o755)
        with os.fdopen(os.open(rules(), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as f:
            f.write(body)
        i = ('INTENT', dict(it, path=rules()))
        c = ('CREATED', ident(rules()))
        recs = {'own': [i, c], 'none': [], 'done': [i, c, ('DONE', {'path': rules()})], 'intent_only': [i],
                'other_ino': [i, ('CREATED', dict(ident(rules()), ino=ident(rules())['ino'] + 1))],
                'other_sha': [('INTENT', dict(it, path=rules(), sha='0' * 64)), c]}[how]
        if recs:
            write_journal(*recs)
        return e

    half = data[:len(data) // 2]
    for name, body, how, want_ok in (
            ('W1 own half-written file (INTENT, CREATED same inode) -> rest appended -> OK', half, 'own', True),
            ('W2 half file, no journal -> REFUSED, untouched', half, 'none', False),
            ('W3 INTENT+CREATED but bytes are not the start of the release -> REFUSED, untouched', b'#!foreign\n',
             'own', False),
            ('W4 INTENT for other bytes (other release) -> REFUSED, untouched', data[:10], 'other_sha', False),
            ('W7 REL4 (A) INTENT, CREATED, DONE (finished earlier) + short prefix -> REFUSED, untouched', half, 'done',
             False),
            ('W8 REL4 (B) INTENT only (no CREATED: not proven ours) + prefix -> REFUSED, untouched', half,
             'intent_only', False),
            ('W9 REL4 CREATED for another inode -> REFUSED, untouched', half, 'other_ino', False)):
        e = half_made(body, how)
        rc, out = quiet(Z.install, e.pkg, commit())
        got = open(rules(), 'rb').read()
        ok = (rc == 0 and 'ZPROBE_355_INSTALL=OK' in out and got == data) if want_ok else \
            (rc == 1 and 'REFUSED' in out and got == body)
        case(name, ok, out)
    e = Env()
    os.mkdir(Z.LIB, 0o700)
    rc, out = quiet(Z.install, e.pkg, commit())
    case('W5 foreign empty 0700 program folder without journal -> REFUSED, mode untouched',
         rc == 1 and 'REFUSED' in out and os.stat(Z.LIB).st_mode & 0o777 == 0o700, out)
    e = Env()
    os.mkdir(Z.LIB, 0o700)
    with open(os.path.join(Z.LIB, 'x'), 'x') as f:
        f.write('x')
    write_journal(('INTENT', {'kind': 'dir', 'path': Z.LIB, 'mode': 0o755, 'who': 'root'}), ('CREATED', ident(Z.LIB)))
    rc, out = quiet(Z.install, e.pkg, commit())
    case('W6 own folder (INTENT, CREATED) that is not empty -> REFUSED, mode untouched',
         rc == 1 and 'REFUSED' in out and os.stat(Z.LIB).st_mode & 0o777 == 0o700, out)
    e = Env()
    os.mkdir(Z.LIB, 0o700)
    write_journal(('INTENT', {'kind': 'dir', 'path': Z.LIB, 'mode': 0o755, 'who': 'root'}), ('CREATED', ident(Z.LIB)))
    rc, out = quiet(Z.install, e.pkg, commit())
    case('W10 own empty 0700 folder (INTENT, CREATED same inode) -> finished -> OK',
         rc == 0 and 'ZPROBE_355_INSTALL=OK' in out and os.stat(Z.LIB).st_mode & 0o777 == 0o755, out)

    # REL5 M-01: the object is swapped or changed after plan() and before apply() acts on it (step "reopen").
    def swap_at_reopen(target, action):
        hit = []

        def fault(st, p, target=target, hit=hit):
            if st == 'reopen' and p == target and not hit:
                hit.append(p)
                action()
        Z.FAULT = fault
        try:
            return quiet(Z.install, e.pkg, commit()) + (bool(hit),)
        finally:
            Z.FAULT = None

    def foreign_file():
        os.rename(rules(), rules() + '.own')          # test only: own half file moves aside inside the temp folder
        with os.fdopen(os.open(rules(), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as f:
            f.write(half)

    e = half_made(half, 'own')
    rc, out, hit = swap_at_reopen(rules(), foreign_file)
    case('S1 REL5 file swapped after plan: foreign file, same bytes and size, other inode -> no write, untouched',
         hit and rc == 1 and 'untouched' in out and open(rules(), 'rb').read() == half
         and open(rules() + '.own', 'rb').read() == half and os.stat(rules()).st_mode & 0o777 == 0o600, out)

    def change_first_byte():
        with open(rules(), 'r+b') as f:
            f.write(b'X')
    e = half_made(half, 'own')
    rc, out, hit = swap_at_reopen(rules(), change_first_byte)
    case('S2 REL5 own file changed after plan (same inode, other first byte) -> no write, untouched',
         hit and rc == 1 and 'untouched' in out and open(rules(), 'rb').read() == b'X' + half[1:]
         and os.stat(rules()).st_mode & 0o777 == 0o600, out)

    def foreign_dir():
        os.rename(Z.LIB, Z.LIB + '.own')              # test only, inside the temp folder
        os.mkdir(Z.LIB, 0o700)
        os.chmod(Z.LIB, 0o700)
    e = Env()
    os.mkdir(Z.LIB, 0o700)
    write_journal(('INTENT', {'kind': 'dir', 'path': Z.LIB, 'mode': 0o755, 'who': 'root'}), ('CREATED', ident(Z.LIB)))
    rc, out, hit = swap_at_reopen(Z.LIB, foreign_dir)
    case('S3 REL5 folder swapped after plan: foreign empty 0700 folder -> no chown/chmod, untouched',
         hit and rc == 1 and 'untouched' in out and os.stat(Z.LIB).st_mode & 0o777 == 0o700
         and not os.listdir(Z.LIB), out)

    def file_inside():
        with open(os.path.join(Z.LIB, 'x'), 'x') as f:
            f.write('x')
    e = Env()
    os.mkdir(Z.LIB, 0o700)
    write_journal(('INTENT', {'kind': 'dir', 'path': Z.LIB, 'mode': 0o755, 'who': 'root'}), ('CREATED', ident(Z.LIB)))
    rc, out, hit = swap_at_reopen(Z.LIB, file_inside)
    case('S4 REL5 own folder got a file after plan -> no chown/chmod, untouched',
         hit and rc == 1 and 'untouched' in out and os.stat(Z.LIB).st_mode & 0o777 == 0o700
         and os.listdir(Z.LIB) == ['x'], out)

    e = Env()
    before = e.created()
    fd = os.open(Z.JOURNAL_DIR, os.O_RDONLY | os.O_DIRECTORY)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        rc, out = quiet(Z.install, e.pkg, commit())
    finally:
        os.close(fd)
    case('X1 REL4 another install holds the lock -> REFUSED, nothing created',
         rc == 1 and 'another install is running' in out and e.created() == before, out)


def t_no_rename():
    import re
    src = open(os.path.join(HERE, 'zprobe_release.py'), encoding='utf-8').read()
    code = '\n'.join(ln for ln in src.splitlines() if not ln.lstrip().startswith('#'))
    bad = re.findall(r'\b(?:os\.(?:rename|renames|replace|unlink|remove|removedirs|rmdir)|shutil\.\w+|renameat2?)\b', code)
    case('C2 REL3 C-01 release code has no rename, move or delete calls', not bad, bad)


def t_names():
    d = tmp()
    a = Z.new_dir(d, '20261113T000000Z', 0o755)
    b = Z.new_dir(d, '20261113T000000Z', 0o755)
    case('N1 L-02 two folders in the same second get different names', a != b and os.path.isdir(a) and os.path.isdir(b))
    if not UNIX:
        skip('N2 (O_NOFOLLOW is Unix only)')
        return
    f1 = Z.new_file(os.path.join(d, 'r-{}.txt'), 's', b'1')
    f2 = Z.new_file(os.path.join(d, 'r-{}.txt'), 's', b'2')
    case('N2 L-02 two reports in the same second get different names, first kept', f1 != f2 and open(f1).read() == '1')


def main():
    t_sql()
    t_tests()
    t_journal()
    t_pins_and_builder()
    t_install()
    t_faults()
    t_no_rename()
    t_names()
    n = sum(RESULTS)
    print(f'ZPROBE_RELEASE_TESTS {n}/{len(RESULTS)} PASS')
    return 0 if n == len(RESULTS) else 1


if __name__ == '__main__':
    sys.exit(main())
