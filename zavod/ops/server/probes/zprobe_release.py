#!/usr/bin/python3
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_release.py
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-13 10:54 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-13 10:54 +02:00
# ИСПОЛНИТЕЛЬ: Claude (чат «Завод 3.5.5 ПБ-1 · 03», сессия 1bcc7ca2-137f-458a-8475-65a3e64abf2d)
# НАЗНАЧЕНИЕ: выпуск пробы ПБ-1 на сервере zavod-1 (проект DESIGN_3_5_5_PB1_v0_13.md §3а, §10, §11; проект выпуска
#   DESIGN_3_5_5_RELEASE). Два режима, запускает только администратор (root) командой оператора:
#   check <пакет>   — проверки §11 только чтением + test_zprobe.py (root, -I -B) в НОВОЙ папке
#                     /var/lib/zavod/probes-tests/<время>; отчёт — новый файл /root/zprobe-check-3.5.5-<время>.txt;
#   install <пакет> — сначала тот же check (любой FAIL — отказ, ничего не поставлено), затем только новые файлы:
#                     учётная запись zprobe (если её нет), /usr/local/lib/zavod/probes (файлы пакета и RELEASE),
#                     /etc/systemd/system/zprobe-run@.service, /var/lib/zavod/probes; уже стоящий тот же файл — без
#                     записи, стоящий другой — отказ. Ничего не запускает (ни службу прогона, ни серию).
#   Итог — строка ZPROBE_355_CHECK=OK|FAIL или ZPROBE_355_INSTALL=OK|ALREADY|REFUSED.
# ОГРАНИЧЕНИЯ: ничего не удаляет, не переименует поверх и не перезаписывает; nft, привратник, посредник, шаблон
#   zagent@ и база только читаются; секретов не читает (файлы из zprobe_rules.CRED_PATHS не открываются).
#   Статус WAIT — факт можно увидеть только пробой на экземпляре-пустышке (отдельный шаг), это не отказ.
import datetime
import hashlib
import json
import os
import pwd
import re
import socket
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zprobe_rules as R  # noqa: E402

LIB = '/usr/local/lib/zavod/probes'
UNIT = '/etc/systemd/system/zprobe-run@.service'
DATA = '/var/lib/zavod/probes'
TESTS = '/var/lib/zavod/probes-tests'
LIB_FILES = {'pb1_session.py': 0o644, 'zprobe_rules.py': 0o644, 'zprobe_runner.py': 0o644,
             'zprobe_journal.py': 0o644, 'zprobe-start': 0o755}
# установленные файлы клетки 3.5.2: путь на сервере → путь в пакете (сверка SHA-256 только чтением, R4 C-03)
CELL = {'/etc/zavod/zavod-egress.nft': 'server/cell/zavod-egress.nft',
        '/usr/local/lib/zavod/zavod-gate': 'server/cell/zavod-gate',
        '/usr/local/lib/zavod/zavod-proxy': 'server/cell/zavod-proxy',
        '/etc/systemd/system/zavod-gate.service': 'server/cell/zavod-gate.service',
        '/etc/systemd/system/zavod-proxy.service': 'server/cell/zavod-proxy.service',
        '/etc/systemd/system/zagent@.service': 'server/cell/zagent@.service'}
PSQL = ['runuser', '-u', 'postgres', '--', 'psql', '-X', '-A', '-t', '-q', '-v', 'ON_ERROR_STOP=1', '-d', 'bem']
DUMMY = 'zagent@' + '0' * 32 + '.service'
OPENED_BY_CHECK = "CHECK ((btrim(opened_by) <> ''::text))"


def sh(*args, timeout=60, inp=None, env=None):
    try:
        p = subprocess.run(list(args), capture_output=True, text=True, timeout=timeout, input=inp, env=env)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired) as x:
        return 127, '', type(x).__name__


def sha(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def ver(text, word):
    m = re.search(re.escape(word) + r' (\d+)\.(\d+)', text or '')
    return (int(m.group(1)), int(m.group(2))) if m else None


def read_pins(path):
    pins = {}
    with open(path, encoding='utf-8') as f:
        for ln in f:
            ln = ln.strip()
            if ln and not ln.startswith('#'):
                k, v = ln.split()
                pins[k] = v
    return pins


class Report:
    def __init__(self):
        self.lines, self.fails, self.waits = [], 0, 0

    def add(self, cid, status, detail):
        detail = ' '.join(str(detail).split())[:300]
        self.lines.append(f'CHECK {cid} {status} {detail}')
        print(self.lines[-1], flush=True)
        self.fails += status == 'FAIL'
        self.waits += status == 'WAIT'


def sql_body(sql_text, name):
    """Текст функции между AS $$ и $$; — ровно то, что PostgreSQL хранит в pg_proc.prosrc."""
    m = re.search(r'CREATE FUNCTION bem_control\.' + name + r'\(.*?\bAS \$\$(.*?)\$\$;', sql_text, re.S)
    return m.group(1) if m else None


def check(pkg, rep, utc):
    ops = os.path.join(pkg, 'zavod', 'ops')
    pins = read_pins(os.path.join(ops, 'zprobe_pins.txt'))
    with open(os.path.join(pkg, 'RELEASE'), encoding='ascii') as f:
        rel = dict(ln.strip().split('=', 1) for ln in f if '=' in ln)
    # 1. выпуск и отпечатки пакета
    bad = [n for n in LIB_FILES if pins.get(n) != sha(os.path.join(ops, 'server', 'probes', n))]
    bad += [n for n, k in (('server/probes/zprobe-run@.service', 'zprobe-run@.service'),
                           ('phone/zprobe_verify.py', 'phone_zprobe_verify.py'),
                           ('server/probes/zprobe_rules.py', 'phone_zprobe_rules.py'),
                           ('pc/zprobe_refs.sh', 'pc_zprobe_refs.sh'), ('pc/zprobe_refs_check.py', 'pc_zprobe_refs_check.py'),
                           ('server/probes/zprobe_rules.py', 'pc_zprobe_rules.py')) if pins.get(k) != sha(os.path.join(ops, n))]
    rep.add('01_package_pins', 'FAIL' if bad or rel.get('commit') != pins.get('release_commit') else 'OK',
            f"release_commit={pins.get('release_commit')} differs={bad}")
    # 2. процессор, ядро, ОС — справка
    rc, osr, _ = sh('cat', '/etc/os-release')
    pretty = re.search(r'PRETTY_NAME="([^"]*)"', osr)
    rep.add('02_platform', 'OK' if os.uname().machine == 'aarch64' else 'FAIL',
            f"{os.uname().machine} kernel={os.uname().release} os={pretty.group(1) if pretty else '?'}")
    # 3. git ≥ 2.37 и клиент ssh
    _, gv, _ = sh('git', '--version')
    rc, _, sv = sh('ssh', '-V')
    g = ver(gv, 'git version')
    rep.add('03_git_ssh', 'OK' if g and g >= (2, 37) and rc == 0 else 'FAIL', f'{gv.strip()} | {sv.strip()}')
    # 4. curl ≥ 7.84 (SOCKS5 через файл-сокет); git-remote-https связан с libcurl
    _, cv, _ = sh('curl', '--version')
    c = ver(cv, 'curl')
    _, ld, _ = sh('ldd', '/usr/lib/git-core/git-remote-https')
    lib = re.search(r'(libcurl[^ ]*)', ld or '')
    rep.add('04_curl', 'OK' if c and c >= (7, 84) and lib else 'FAIL',
            f"{(cv.splitlines() or ['absent'])[0]} | git-remote-https -> {lib.group(1) if lib else 'no libcurl'}")
    # 5. таблица nft построчно равна NFT_EXPECTED (R4)
    rc, nft, err = sh('nft', 'list', 'table', 'inet', 'zavod')
    why = R.nft_problem(nft) if rc == 0 else f'nft_rc_{rc} {err.strip()}'
    rep.add('05_nft_table', 'FAIL' if why else 'OK', why or 'chains output, egress_closed equal NFT_EXPECTED')
    # 6. строка ядра zavod-egress-refused с SRC, DST, SPT, DPT (последняя за 30 дней)
    rc, kj, _ = sh('journalctl', '-k', '--no-pager', '-o', 'json', '--since', '-30d', '--grep', 'zavod-egress-refused',
                   timeout=120)
    msgs = []
    for ln in (kj or '').splitlines():
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        if isinstance(e.get('MESSAGE'), str) and e['MESSAGE'].startswith(R.KLOG_PREFIX):
            msgs.append(e)
    if msgs:
        k = R.parse_klog(msgs[-1]['MESSAGE'])
        rep.add('06_kernel_refused_line', 'OK' if k and '__REALTIME_TIMESTAMP' in msgs[-1] else 'FAIL',
                f'lines={len(msgs)} last={k}')
    else:
        rep.add('06_kernel_refused_line', 'WAIT', 'no refused packet in 30 days; seen only after a trial refusal')
    # 7. установленные файлы клетки = файлам коммита выпуска (только чтение)
    for path, rel_p in sorted(CELL.items()):
        want = sha(os.path.join(ops, rel_p))
        try:
            got = sha(path)
        except OSError as x:
            got = type(x).__name__
        key = os.path.basename(path)
        pin = pins.get(key)
        ok = got == want and (pin is None or pin == want)
        rep.add('07_cell_' + key, 'OK' if ok else 'FAIL', f'installed={got[:16]} commit={want[:16]} pin={(pin or "-")[:16]}')
    # 8. часы синхронизированы
    _, ts, _ = sh('timedatectl', 'show', '-p', 'NTPSynchronized', '--value')
    rep.add('08_clock', 'OK' if ts.strip() == 'yes' else 'FAIL', f'NTPSynchronized={ts.strip() or "?"}')
    # 9. функция lease_reserve_start = 06_zavod_ext_04.sql; столбец opened_by принимает zprobe-run
    with open(os.path.join(pkg, 'zavod', 'kernel', 'db', '06_zavod_ext_04.sql'), encoding='utf-8') as f:
        body = sql_body(f.read(), 'lease_reserve_start')
    rc, src, err = sh(*PSQL, inp="SELECT prosrc FROM pg_proc WHERE oid = "
                      "'bem_control.lease_reserve_start(uuid)'::regprocedure;")
    same = rc == 0 and body is not None and src.rstrip('\n') == body
    rep.add('09_lease_reserve_start', 'OK' if same else 'FAIL',
            f'rc={rc} sql_sha={hashlib.sha256((body or "").encode()).hexdigest()[:16]} '
            f'db_sha={hashlib.sha256(src.rstrip(chr(10)).encode()).hexdigest()[:16]} {err.strip()}')
    rc, cdef, err = sh(*PSQL, inp="SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                       "WHERE conrelid = 'bem_control.chat_lease'::regclass AND conname = 'chat_lease_opened_by_check';")
    rep.add('09_opened_by', 'OK' if cdef.strip() == OPENED_BY_CHECK else 'FAIL', f'rc={rc} {cdef.strip()} {err.strip()}')
    # 10. /proc/<pid>/stat даёт время запуска (поле 22)
    try:
        with open('/proc/self/stat', encoding='ascii') as f:
            st = f.read()
        start_time = int(st[st.rindex(')') + 2:].split()[19])
        rep.add('10_proc_start_time', 'OK', f'field22={start_time}')
    except (OSError, ValueError, IndexError) as x:
        rep.add('10_proc_start_time', 'FAIL', type(x).__name__)
    # 11. экземпляр-пустышка шаблона — справка до и после (сравнивает zprobe_runner)
    _, dm, _ = sh('systemctl', 'show', DUMMY, '-p', 'LoadState', '-p', 'ActiveState', '-p', 'DropInPaths')
    rep.add('11_dummy_instance', 'OK' if 'LoadState=loaded' in dm else 'FAIL', dm.replace('\n', ' '))
    # 12. посредник пишет peer, uid, cgroup (последние 500 строк его журнала)
    _, pj, _ = sh('journalctl', '-u', 'zavod-proxy.service', '--no-pager', '-o', 'cat', '-n', '500')
    recs = [ln for ln in pj.splitlines() if ln.startswith('ZAVOD_PROXY {')]
    full = [ln for ln in recs if all(f'"{k}":' in ln for k in ('peer', 'uid', 'cgroup'))]
    _, pa, _ = sh('systemctl', 'is-active', 'zavod-proxy.service')
    rep.add('12_proxy', 'FAIL' if pa.strip() != 'active' else ('OK' if full else 'WAIT'),
            f'active={pa.strip()} records={len(recs)} with_peer_uid_cgroup={len(full)}')
    # 13. хост сам выходит к GitHub на 22 и 443 (только соединение, без данных)
    res = []
    for port in R.PORTS:
        try:
            with socket.create_connection(('github.com', port), timeout=8):
                res.append(f'{port}=OK')
        except OSError as x:
            res.append(f'{port}={type(x).__name__}')
    rep.add('13_host_to_github', 'OK' if all(r.endswith('=OK') for r in res) else 'FAIL', ' '.join(res))
    # 14. испытания в НОВОЙ папке (R6B C-02: это запись новых файлов, не «только чтение»); от root, -I -B
    os.makedirs(TESTS, mode=0o755, exist_ok=True)
    troot = os.path.join(TESTS, utc)
    os.mkdir(troot, 0o700)
    env = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8', 'ZPROBE_TEST_ROOT': troot}
    rc, out, err = sh('python3', '-I', '-B',
                      os.path.join(ops, 'server', 'probes', 'test_zprobe.py'), timeout=600, env=env)
    with open(os.path.join(TESTS, utc + '.out'), 'x', encoding='utf-8') as f:
        f.write(out + err)
    last = (out.strip().splitlines() or [''])[-1]
    skips = [ln for ln in out.splitlines() if ln.startswith('SKIP') and not ln.startswith('SKIP 174, 175 (Windows only)')]
    m = re.fullmatch(r'ZPROBE_TESTS (\d+)/(\d+) PASS', last)
    rep.add('14_tests', 'OK' if rc == 0 and m and m.group(1) == m.group(2) and not skips else 'FAIL',
            f'rc={rc} {last} unexpected_skips={len(skips)} out={troot}.out')
    return rel, pins


def write_report(rep, utc, mode):
    path = f'/root/zprobe-{mode}-3.5.5-{utc}.txt'
    with open(path, 'x', encoding='utf-8') as f:
        f.write('\n'.join(rep.lines) + '\n')
    os.chmod(path, 0o600)
    print(f'REPORT={path} SHA256={sha(path)}')


def put_same(path, data, mode, uid=0, gid=0):
    """Новый файл (O_EXCL); тот же байт в байт — ничего не делать; другой — отказ."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    except FileExistsError:
        if os.path.islink(path) or not os.path.isfile(path) or sha(path) != hashlib.sha256(data).hexdigest():
            raise SystemExit(f'ZPROBE_355_INSTALL=REFUSED {path} exists and differs; nothing replaced')
        return 'same'
    with os.fdopen(fd, 'wb') as f:
        f.write(data)
    os.chown(path, uid, gid)
    os.chmod(path, mode)
    return 'new'


def install(pkg, rel, pins):
    ops = os.path.join(pkg, 'zavod', 'ops')
    done = []
    try:
        zp = pwd.getpwnam('zprobe')
        if zp.pw_uid >= 1000 or not zp.pw_shell.endswith('nologin'):
            raise SystemExit('ZPROBE_355_INSTALL=REFUSED user zprobe exists but is not a system nologin account')
    except KeyError:
        rc, _, err = sh('useradd', '--system', '--user-group', '--no-create-home', '--home-dir', '/nonexistent',
                        '--shell', '/usr/sbin/nologin', 'zprobe')
        if rc != 0:
            raise SystemExit(f'ZPROBE_355_INSTALL=REFUSED useradd rc={rc} {err.strip()}')
        zp = pwd.getpwnam('zprobe')
        done.append('user zprobe')
    for d, mode, uid, gid in ((LIB, 0o755, 0, 0), (DATA, 0o750, zp.pw_uid, zp.pw_gid)):
        if os.path.islink(d):
            raise SystemExit(f'ZPROBE_355_INSTALL=REFUSED {d} is a link')
        if not os.path.isdir(d):
            os.mkdir(d, mode)
            os.chown(d, uid, gid)
            os.chmod(d, mode)
            done.append(d)
    for n, mode in LIB_FILES.items():
        with open(os.path.join(ops, 'server', 'probes', n), 'rb') as f:
            if put_same(os.path.join(LIB, n), f.read(), mode) == 'new':
                done.append(n)
    if put_same(os.path.join(LIB, 'RELEASE'), f"commit={rel['commit']}\nversion=3.5.5\n".encode(), 0o644) == 'new':
        done.append('RELEASE')
    with open(os.path.join(ops, 'server', 'probes', 'zprobe-run@.service'), 'rb') as f:
        if put_same(UNIT, f.read(), 0o644) == 'new':
            done.append(UNIT)
    sh('systemctl', 'daemon-reload')
    # сверка установленного с отпечатками выпуска и разбор службы
    bad = [n for n in LIB_FILES if sha(os.path.join(LIB, n)) != pins.get(n)]
    bad += [] if sha(UNIT) == pins.get('zprobe-run@.service') else [UNIT]
    rc, vout, verr = sh('systemd-analyze', 'verify', 'zprobe-run@check.service')
    _, rw, _ = sh('systemctl', 'show', 'zprobe-run@check.service', '-p', 'ReadWritePaths', '-p', 'User')
    print(f'INSTALLED_NEW={done or "nothing (already installed)"}')
    print(f'PINS_DIFFER={bad} VERIFY_RC={rc} {(vout + verr).strip()[:300]} {rw.replace(chr(10), " ")}')
    if bad or rc != 0 or f'ReadWritePaths={DATA}' not in rw:
        raise SystemExit('ZPROBE_355_INSTALL=REFUSED installed files or unit do not match the release')
    print('ZPROBE_355_INSTALL=' + ('OK' if done else 'ALREADY') + f" release={rel['commit']}")


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ('check', 'install') or os.geteuid() != 0:
        print('usage (root): zprobe_release.py check|install <package dir>')
        return 2
    pkg = os.path.abspath(sys.argv[2])
    utc = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    rep = Report()
    rel, pins = check(pkg, rep, utc)
    write_report(rep, utc, 'check')
    print(f'ZPROBE_355_CHECK={"FAIL" if rep.fails else "OK"} fails={rep.fails} waits={rep.waits}')
    if sys.argv[1] == 'check':
        return 1 if rep.fails else 0
    if rep.fails:
        print('ZPROBE_355_INSTALL=REFUSED check has FAIL lines; nothing installed')
        return 1
    install(pkg, rel, pins)
    return 0


if __name__ == '__main__':
    sys.exit(main())
