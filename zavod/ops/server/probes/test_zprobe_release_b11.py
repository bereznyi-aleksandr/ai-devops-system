#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_release_b11.py
# ВЕРСИЯ: v0.5 (выпуск B11)  СТАТУС: DRAFT
# v0.5 (2026-11-17 18:59 +02:00, Claude, терминал zavod; REL99 M-355-REL99-01): V19 — TOOL zprobe-r2-b11-0.3.
# v0.4 (2026-11-17 18:22 +02:00, Claude, терминал zavod (58f8b71b); REL98 L-355-REL98-01): во временных фикстурах нет ни
#   удаления, ни переименования, ни перезаписи. put() создаёт только новый файл (режим 'xb': файл уже есть — ошибка).
#   Каждый отрицательный случай строится в своём новом дереве: пакет — fake_pkg(over, skip) (нужный файл сразу с другими
#   байтами или не создаётся), дерево B10 — fake_b10(.., over, modes) (файл сразу с другими байтами или правами), V23 —
#   копия папки B11 без двух файлов и новые файлы в ней. V25 — статическая проверка (разбор исходника, до CI и без root):
#   в этом файле и в test_zprobe_r2_b11.py нет вызовов os/shutil rename, replace, remove, unlink, rmdir, removedirs,
#   rmtree, move, truncate; open() — только 'rb' или 'xb'; os.open с O_CREAT — только с O_EXCL, без O_TRUNC и O_APPEND;
#   в помощниках из файлов B10 (test_zprobe_r2.mk, test_zprobe_export.put0600) — тех же вызовов удаления и переименования нет.
#   V19 — TOOL zprobe-r2-b11-0.2.
# v0.3 (2026-11-17 17:33 +02:00, Claude, терминал zavod): V19 — checks-0.6 и паспорт zprobe_checks.py v0.6.
# v0.2 (2026-11-17 07:51 +02:00, Claude, терминал zavod, помощник; REL97 L-355-REL97-02): четыре os.remove и os.rmdir во
#   временных фикстурах убраны — каждый случай идёт в своей свежей временной папке или через переименование в
#   *.SUPERSEDED (ничего не удаляется даже в папках испытания); V19 — версия проверок checks-0.5, паспорт v0.5.
# ДАТА СОЗДАНИЯ: 2026-11-17 07:04 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-17 07:04 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминальный чат zavod (ee9861cd)
# НАЗНАЧЕНИЕ: проверки установщика B11 (zprobe_release_b11.py) и сборщика B11 (build_release_3_5_5_b11.py), решение
#   аудита REL96B PATH=A, по образцу test_zprobe_release_b10.py. Без root (везде, где есть Linux): пути, состав папки
#   probes-b11 (ровно модули, которые транзитивно импортирует zprobe_r2.py — состав считается разбором исходников),
#   служб нет, цели и формат INSTALLED.sha256, состав пакета (модули кроме checks и r2 равны отпечаткам B10), список
#   INSTALLED.sha256 B10 пересобирается из настоящих отпечатков и даёт ту же сумму, что на сервере, проверка «B10 цел»
#   (изменённый файл, служба, лишний файл, RELEASE, INSTALLED, права, нет B10 — всё FAIL), порядок списка проверок,
#   сборщик. Только Linux root (в CI — sudo): создание целей настоящим проходом установки в папке испытания — повтор
#   ничего не создаёт и не перезаписывает, подмена файла видна, записи только в probes-b11 и в дневник.
#   Строки: CASE <Vnn_имя> PASS|FAIL|SKIP. Итог: ZPROBE_RELEASE_B11_TEST=PASS | PASS_NO_ROOT | FAIL.
# ОГРАНИЧЕНИЯ: пишет только в новые временные папки (ZPROBE_TEST_ROOT, если задан); ничего не удаляет.
import ast
import hashlib
import os
import posixpath
import shutil
import stat
import sys
import tempfile
import types

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
UNIX = hasattr(os, 'getuid')
if not UNIX:   # Windows: модулей pwd/grp/fcntl нет — заглушки, вызываются только чистые функции
    for _m in ('pwd', 'grp', 'fcntl'):
        sys.modules.setdefault(_m, types.ModuleType(_m))
    os.path.join = posixpath.join    # пути целей — серверные: соединяются через «/»
ROOT = UNIX and os.geteuid() == 0 and sys.platform.startswith('linux')
sys.path.insert(0, HERE)
import zprobe_release_b11 as M  # noqa: E402
import build_release_3_5_5_b11 as BB  # noqa: E402

B10, B9, REL = M.B10, M.B9, M.REL
OK, SKIPPED = True, 0
PROBES = os.path.join(REPO, 'zavod', 'ops', 'server', 'probes')
# настоящий список установленных файлов B10 на сервере (STAGE_AND_PREFLIGHT / r2_precheck.sh v0.4, 16.11): суммы
SERVER_B10 = {'RELEASE': 'd100a7ee65a75ad10b9263c5b823ceae09d73c722bd7ff2f3e7448569bcabe45',
              'zprobe_pins_b9.txt': '91ed266ae21a3719463a4b49d20c5d9f5ed797cd6dbbdaf9dbbaa60d4fbaa712',
              'INSTALLED.sha256': 'addd580d99788504ba396dd24ca5e602c171a90d3852f79975b0c4a72f238934'}


def case(name, cond, detail=''):
    global OK
    OK &= bool(cond)
    print('CASE', name, 'PASS' if cond else 'FAIL ' + f'-> {detail}'[:300], flush=True)


def skip(name, why='needs Linux'):
    global SKIPPED
    SKIPPED += 1
    print('CASE', name, f'SKIP ({why})', flush=True)


def tmp():
    return tempfile.mkdtemp(prefix='zrel11-', dir=os.environ.get('ZPROBE_TEST_ROOT') or None)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def read(p):
    with open(p, 'rb') as f:
        return f.read()


def put(p, b, mode=0o644):
    """Только новый файл (REL98 L-01): режим 'xb' — существующий файл не перезаписывается, а даёт ошибку."""
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'xb') as f:
        f.write(b)
    os.chmod(p, mode)


def import_closure(start):
    """Модули zprobe_*.py, которые транзитивно импортирует start (разбор исходников: import и from .. import)."""
    seen, todo = set(), [start]
    while todo:
        n = todo.pop()
        if n in seen:
            continue
        seen.add(n)
        tree = ast.parse(read(os.path.join(PROBES, n)).decode('utf-8'))
        for node in ast.walk(tree):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
            for m in names:
                if m.startswith('zprobe_') and os.path.isfile(os.path.join(PROBES, m + '.py')):
                    todo.append(m + '.py')
    return seen


def fake_pkg(over=None, skip=()):
    """Пакет в новой папке испытания: модули B11 из дерева, RELEASE, отпечатки B9 и B10 из дерева. over — {имя модуля или
    путь отпечатков: байты} (файл сразу с другими байтами), skip — что не создавать (REL98 L-01: без перезаписи и удаления)."""
    over = over or {}
    pkg = tmp()
    src = os.path.join(pkg, 'zavod', 'ops', 'server', 'probes')
    for n in M.LIB_FILES:
        if n not in skip:
            put(os.path.join(src, n), over.get(n, read(os.path.join(PROBES, n))))
    put(os.path.join(pkg, 'RELEASE'), b'commit=' + b'b' * 40 + b'\nversion=3.5.5-b11\n')
    for rel in (M.PINS_B9_SRC, M.PINS_B10_SRC):
        if rel not in skip:
            put(os.path.join(pkg, rel), over.get(rel, read(os.path.join(REPO, rel))))
    return pkg


def set_lib(lib):
    M.LIB = lib
    REL.LIB = lib


def t_names():
    case('V01_lib_and_no_units_b11', M.LIB == '/usr/local/lib/zavod/probes-b11' and REL.LIB == M.LIB
         and REL.JOURNAL_PREFIX == 'zprobe-install-3.5.5-b11-' and REL.TESTS == '/var/lib/zavod/probes-tests-b11'
         and M.UNITS == () and B9.targets is M.targets and M.INSTALLED_NAME == 'INSTALLED.sha256'
         and B10.LIB == '/usr/local/lib/zavod/probes-b10' and B10.B9_LIB == '/usr/local/lib/zavod/probes-b9',
         (M.LIB, REL.LIB, REL.JOURNAL_PREFIX))
    closure = import_closure('zprobe_r2.py')
    case('V02_modules_are_exactly_the_imports_of_zprobe_r2', closure == set(M.MODULES) and set(M.LIB_FILES) == closure
         and len(M.MODULES) == len(set(M.MODULES)) == 7 and set(M.CHANGED) == {'zprobe_checks.py', 'zprobe_r2.py'}
         and all(m == 0o644 for m in M.LIB_FILES.values()), sorted(closure ^ set(M.MODULES)))


def t_targets():
    pkg = fake_pkg()
    tg = M.targets(pkg)
    paths = [p for p, _, _ in tg]
    lib = M.LIB
    want = {lib} | {os.path.join(lib, n) for n in M.LIB_FILES} | {os.path.join(lib, n) for n in (
        'RELEASE', M.PINS_B9_NAME, M.INSTALLED_NAME)}
    modes = {p: m for p, _, m in tg}
    data = dict((p, d) for p, d, _ in tg)
    case('V03_targets_b11', tg[0] == (lib, None, 0o755) and paths[-1] == os.path.join(lib, 'INSTALLED.sha256')
         and set(paths) == want and len(paths) == len(want) == 11 and all(modes[p] == 0o644 for p in paths[1:])
         and not any(p.startswith('/etc/') for p in paths)
         and data[os.path.join(lib, M.PINS_B9_NAME)] == read(os.path.join(REPO, 'zavod', 'ops', 'zprobe_pins_b9.txt'))
         and data[os.path.join(lib, 'zprobe_checks.py')] == read(os.path.join(PROBES, 'zprobe_checks.py')),
         sorted(set(paths) ^ want))
    text = tg[-1][1].decode('ascii')
    lines = text.split('\n')
    got, fmt_ok = {}, text.endswith('\n') and lines[-1] == ''
    for ln in lines[:-1]:
        m = B10.UN.INSTALLED_LINE.fullmatch(ln)
        if not m:
            fmt_ok = False
            break
        got[m.group(2)] = m.group(1)
    order = [ln.split('  ', 1)[1] for ln in lines[:-1]]
    files = {p: d for p, d, _ in tg[:-1] if d is not None}
    case('V04_installed_list_format', fmt_ok and order == sorted(order) and len(order) == len(set(order)) == 9
         and got == {p: sha(d) for p, d in files.items()} and paths[-1] not in got
         and 'zprobe-run-b10@' not in text, text[:200])
    return pkg


def t_pkg_modules():
    p0 = M.pkg_problems(fake_pkg())
    chg = {'zprobe_checks.py': b'# another checks\n', 'zprobe_r2.py': b'# another r2\n'}   # изменённые модули — разрешены
    p1 = M.pkg_problems(fake_pkg(chg))
    seal_x = read(os.path.join(PROBES, 'zprobe_seal.py')) + b'# x\n'
    p2 = M.pkg_problems(fake_pkg(dict(chg, **{'zprobe_seal.py': seal_x})))
    p3 = M.pkg_problems(fake_pkg({'zprobe_seal.py': seal_x}, skip=('zprobe_dropin.py',)))   # модуля B10 нет с самого начала
    p4 = M.pkg_problems(fake_pkg(skip=(M.PINS_B10_SRC,)))
    case('V05_package_modules_equal_b10_pins_except_checks_and_r2', p0 == [] and p1 == []
         and p2 == ['package zprobe_seal.py differs from B10 pins']
         and len(p3) == 2 and 'zprobe_dropin.py' in p3[1] and len(p4) == 1 and 'B10 pins' in p4[0], (p0, p1, p2, p3, p4))


def t_b10_expected():
    pkg = fake_pkg()
    pins = M.pins10(pkg)
    lst, rel = M.b10_installed_expected(pkg, pins)
    rows = lst.decode('ascii').split('\n')[:-1]
    case('V06_b10_installed_list_rebuilt_equals_server_sum', sha(lst) == SERVER_B10['INSTALLED.sha256']
         and sha(rel) == SERVER_B10['RELEASE'] and sha(read(os.path.join(pkg, M.PINS_B9_SRC))) == SERVER_B10['zprobe_pins_b9.txt']
         and len(rows) == 17 and rows == sorted(rows, key=lambda r: r.split('  ', 1)[1]),
         (sha(lst), sha(rel), len(rows)))


def fake_b10(base, pkg, over=None, modes=None):
    """Дерево B10 в новой папке испытания, отпечатки B10 к нему (ключи — как у настоящего zprobe_pins_b10.txt). Пакет —
    без отпечатков B10 (fake_pkg(skip=..)): их пишет эта функция. over — {имя: функция(байты) → байты}: файл сразу пишется
    с другими байтами, отпечаток — от исходных; modes — {имя: права} (REL98 L-01: без перезаписи)."""
    over, modes = over or {}, modes or {}

    def bytes_of(k, b):
        return over[k](b) if k in over else b
    lib, ud = B10.LIB, B10.UNIT_DIR
    os.makedirs(lib)
    os.makedirs(ud, exist_ok=True)
    pins = {k: 'e' * 64 for k in M.B10_PIN_KEYS}
    commit = 'c' * 40
    for k, mode in B10.LIB_FILES.items():
        b = f'# b10 {k}\nX = 1\n'.encode()
        put(os.path.join(lib, k), bytes_of(k, b), modes.get(k, mode))
        pins[k] = sha(b)
    for u in B10.UNITS:
        b = f'[Unit]\nDescription={u}\n'.encode()
        put(os.path.join(ud, u), bytes_of(u, b))
        pins[u] = sha(b)
    body = '# pins B10\nrelease_commit ' + commit + '\n' + ''.join(f'{k} {v}\n' for k, v in pins.items())
    put(os.path.join(pkg, M.PINS_B10_SRC), body.encode())
    lst, rel = M.b10_installed_expected(pkg, M.pins10(pkg))
    put(os.path.join(lib, 'RELEASE'), bytes_of('RELEASE', rel))
    put(os.path.join(lib, M.PINS_B9_NAME), bytes_of(M.PINS_B9_NAME, read(os.path.join(pkg, M.PINS_B9_SRC))))
    put(os.path.join(lib, M.INSTALLED_NAME), bytes_of(M.INSTALLED_NAME, lst))
    return lib, ud


def t_b10_check():
    names = ('V07_b10_untouched_ok', 'V08_b10_changed_file_flagged', 'V09_b10_changed_unit_flagged',
             'V10_b10_extra_file_or_pycache_flagged', 'V11_b10_release_installed_pins_copy_mode_flagged',
             'V12_b10_missing_flagged', 'V13_b10_pin_keys_equal_real_b10_pins')
    real = set(B9.read_pins_file(os.path.join(REPO, M.PINS_B10_SRC), M.B10_PIN_KEYS))
    case(names[6], real == set(M.B10_PIN_KEYS) | {'release_commit'})
    if not UNIX:
        for n in names[:6]:
            skip(n)
        return
    base, pkg = tmp(), fake_pkg(skip=(M.PINS_B10_SRC,))
    keep = (B10.LIB, B10.UNIT_DIR, REL.ROOT_UID, REL.ROOT_GID)
    lib, ud = os.path.join(base, 'probes-b10'), os.path.join(base, 'sd')
    REL.ROOT_UID, REL.ROOT_GID = os.getuid(), os.getgid()

    def variant(over=None, modes=None):
        """Отдельное новое дерево B10 и свой пакет: файл сразу с другими байтами или правами (REL98 L-01)."""
        vbase, vpkg = tmp(), fake_pkg(skip=(M.PINS_B10_SRC,))
        B10.LIB, B10.UNIT_DIR = os.path.join(vbase, 'probes-b10'), os.path.join(vbase, 'sd')   # до fake_b10: пути — в списке
        fake_b10(vbase, vpkg, over, modes)
        return M.b10_problems(vpkg), B10.LIB, B10.UNIT_DIR
    try:
        p1, lib1, _ud1 = variant({'zprobe_checks.py': lambda b: b + b'# changed\n'})
        rp1 = os.path.join(lib1, 'zprobe_checks.py')
        p2, _lib2, ud2 = variant({'zprobe-run-b10@.service': lambda b: b + b'ExecStart=/bin/false\n'})
        up = os.path.join(ud2, 'zprobe-run-b10@.service')
        bad, bad_lib = {}, {}
        for n in ('RELEASE', M.INSTALLED_NAME, M.PINS_B9_NAME):
            bad[n], bad_lib[n], _u = variant({n: lambda b: b + b'x'})
        bad['mode'], lib_m, _u = variant(modes={'zprobe_checks.py': 0o666})
        rp = os.path.join(lib_m, 'zprobe_checks.py')
        B10.LIB, B10.UNIT_DIR = lib, ud                     # основное дерево — для V07, V10, V12 и V14
        fake_b10(base, pkg)
        p0 = M.b10_problems(pkg)
        case(names[0], p0 == [], p0)
        case(names[1], p1 == [f'B10 {rp1} differs from B10 pins'], p1)
        case(names[2], p2 == [f'B10 {up} differs from B10 pins'], p2)
        lib3a, lib3b = os.path.join(base, 'probes-b10-extra'), os.path.join(base, 'probes-b10-pyc')
        shutil.copytree(lib, lib3a)            # отдельные копии: ни файл, ни папка после проверки не удаляются
        shutil.copytree(lib, lib3b)
        put(os.path.join(lib3a, 'zprobe_extra.py'), b'x\n')
        os.mkdir(os.path.join(lib3b, '__pycache__'))
        B10.LIB = lib3a
        p3a = [x for x in M.b10_problems(pkg) if M.INSTALLED_NAME not in x]   # список копии несёт пути исходной папки
        B10.LIB = lib3b
        p3b = [x for x in M.b10_problems(pkg) if M.INSTALLED_NAME not in x]
        B10.LIB = lib
        case(names[3], len(p3a) == 1 and 'holds other files' in p3a[0] and 'zprobe_extra.py' in p3a[0]
             and len(p3b) == 1 and '__pycache__' in p3b[0], (p3a, p3b))
        case(names[4], all(len(v) == 1 and 'differs' in v[0] for v in bad.values()) and len(bad) == 4
             and 'owner or mode' in bad['mode'][0] and bad['mode'][0].startswith(f'B10 {rp}'), bad)
        lib2 = os.path.join(base, 'probes-b10-r')
        shutil.copytree(lib, lib2, ignore=shutil.ignore_patterns('zprobe_seal.py'))
        B10.LIB = lib2
        p5 = M.b10_problems(pkg)
        B10.LIB = os.path.join(base, 'none')
        p6 = M.b10_problems(pkg)
        p5 = [x for x in p5 if M.INSTALLED_NAME not in x]       # копия папки несёт пути исходной: список в ней другой
        case(names[5], len(p5) == 1 and 'zprobe_seal.py' in p5[0] and len(p6) > 12 and all('B10' in x for x in p6),
             (p5, p6[:2]))
        B10.LIB = lib
        t_common(pkg, base)
    finally:
        B10.LIB, B10.UNIT_DIR, REL.ROOT_UID, REL.ROOT_GID = keep


def t_common(pkg, base):
    """Список проверок: PKG_MODULES, B8, B9, B10, UNITS, ACCOUNT, JOURNAL, STARTED; B10 FAIL виден как FAIL."""
    keep = (B9.b8_problems, B10.b9_problems, B9.units_problems, B9.account_problems, B9.journal_problems,
            B9.started_problems, B10.pycache_problems, M.pkg_problems)
    ns = types.SimpleNamespace(pw_uid=1)
    B9.b8_problems, B10.b9_problems, B9.units_problems = (lambda _p: []), (lambda _p: []), (lambda: [])
    B9.account_problems, B9.journal_problems = (lambda: ([], ns)), (lambda: ([], 'journal'))
    B9.started_problems, B10.pycache_problems = (lambda _zp: []), (lambda: ([], []))
    M.pkg_problems = lambda _p: []          # состав пакета здесь не проверяется (отпечатки B10 пакета — пробные)
    try:
        rep = REL.Report()
        zp = M.common(pkg, rep)
        rep2 = REL.Report()
        keep_lib = B10.LIB
        B10.LIB = os.path.join(base, 'probes-b10-nodropin')       # копия папки B10 без zprobe_dropin.py (не удаление)
        shutil.copytree(keep_lib, B10.LIB, ignore=shutil.ignore_patterns('zprobe_dropin.py'))
        try:
            M.common(pkg, rep2)
        finally:
            B10.LIB = keep_lib
        ids = [ln.split()[1] for ln in rep.lines]
        case('V14_common_order_and_b10_fail', zp is ns and ids == ['PKG_MODULES', 'B8', 'B9', 'B10', 'UNITS', 'ACCOUNT',
                                                                    'JOURNAL', 'STARTED']
             and rep.fails == 0 and rep2.fails == 1 and rep2.lines[3].startswith('CHECK B10 FAIL'), (rep.lines, rep2.lines))
    finally:
        (B9.b8_problems, B10.b9_problems, B9.units_problems, B9.account_problems, B9.journal_problems,
         B9.started_problems, B10.pycache_problems, M.pkg_problems) = keep


def t_builder():
    B = BB.B
    P = B.PROBES
    files, keys = set(B.FILES), dict(B.PIN_KEYS)
    need = {P + n for n in M.MODULES} | {P + n for n in ('zprobe_journal.py', 'zprobe_release.py', 'zprobe_release_b9.py',
                                                         'zprobe_release_b10.py', 'zprobe_release_b11.py')} | {
        'zavod/ops/zprobe_pins_b8.txt', 'zavod/ops/zprobe_pins_b9.txt', 'zavod/ops/zprobe_pins_b10.txt'}
    missing = sorted(need - files) + sorted(f for f in B.FILES if not os.path.isfile(os.path.join(REPO, f)))
    inst = import_closure('zprobe_release_b11.py')
    case('V15_builder_files_cover_installer_imports', not missing and len(B.FILES) == len(files)
         and need == files and {n for n in inst} <= {os.path.basename(f) for f in B.FILES}
         and not any('b9@' in f or 'b10@' in f or 'cell' in f or f.endswith('.sql') for f in B.FILES),
         (missing, sorted(files ^ need)))
    want_keys = set(M.MODULES) | {'zprobe_pins_b9.txt'}
    case('V16_builder_pin_keys', set(keys) == want_keys and len(keys) == len(B.PIN_KEYS) == 8
         and all(p in files for p in keys.values()), sorted(set(keys) ^ want_keys))
    case('V17_builder_names', B.VERSION == '3.5.5-b11' and B.PINS_PATH == 'zavod/ops/zprobe_pins_b11.txt'
         and B.SH_PATH == P + 'zprobe-release-3.5.5-b11.sh' and (P + 'zprobe_release_b11.py') in B.EXEC
         and 'zprobe_release_b11.py" "$M"' in B.SH_TEMPLATE and 'ВЫПУСК: 3.5.5 B11' in B.SH_TEMPLATE
         and 'zprobe_release_b10.py' not in B.SH_TEMPLATE and 'zprobe_release_b9.py' not in B.SH_TEMPLATE)
    tree = lambda p: read(os.path.join(REPO, p))  # noqa: E731
    pins10 = BB.B9B.parse(tree('zavod/ops/zprobe_pins_b10.txt'))
    changed = lambda p: b'# changed\n' if p.endswith('zprobe_seal.py') else tree(p)  # noqa: E731
    case('V18_builder_refuses_changed_module_except_checks_and_r2', BB.unchanged_problem(pins10, tree) is None
         and 'zprobe_seal.py' in (BB.unchanged_problem(pins10, changed) or '')
         and BB.unchanged_problem(pins10, lambda p: b'x' if p.endswith(('zprobe_checks.py', 'zprobe_r2.py'))
                                  else tree(p)) is None
         and BB.unchanged_problem({k: v for k, v in pins10.items() if k != 'zprobe_rules.py'}, tree) is not None)


def t_code():
    def code(n):
        return '\n'.join(ln for ln in read(os.path.join(PROBES, n)).decode('utf-8').split('\n') if not ln.startswith('#'))
    r2, ck = code('zprobe_r2.py'), code('zprobe_checks.py')
    head = read(os.path.join(PROBES, 'zprobe_checks.py')).decode('utf-8').split('\n')[2]
    import zprobe_r2 as R2
    case('V19_r2_b11_names_and_checks_version_in_proof_tool', 'probes-b10' not in r2
         and "'pins_b9': '/usr/local/lib/zavod/probes-b11/zprobe_pins_b9.txt'" in r2 and R2.TOOL == 'zprobe-r2-b11-0.3'
         and R2.TOOL_VERSION == 'zprobe-r2-b11-0.3.checks-0.6' and head.startswith('# ВЕРСИЯ: v0.6 (выпуск B11)')
         and R2.CHECKS_VERSION == 'checks-' + head.split('v', 1)[1].split(' ')[0]
         and R2.PATHS['pins_b9'] == '/usr/local/lib/zavod/probes-b11/zprobe_pins_b9.txt'
         and "'tool_version': TOOL_VERSION" in r2 and 'PIN_B9' in ck, (head, R2.TOOL_VERSION))


FORBIDDEN = {'rename', 'replace', 'remove', 'unlink', 'rmdir', 'removedirs', 'rmtree', 'move', 'truncate', 'ftruncate',
             'renames'}


def forbidden_calls(tree, strict_open=True):
    """Вызовы os./shutil. из FORBIDDEN; open() не 'rb'/'xb'; os.open с O_CREAT без O_EXCL или с O_TRUNC/O_APPEND."""
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id in ('os', 'shutil') \
                and fn.attr in FORBIDDEN:
            bad.append(f'{node.lineno}:{fn.value.id}.{fn.attr}')
        if strict_open and isinstance(fn, ast.Name) and fn.id == 'open':
            mode = node.args[1] if len(node.args) > 1 else next((k.value for k in node.keywords if k.arg == 'mode'), None)
            if mode is not None and not (isinstance(mode, ast.Constant) and mode.value in ('rb', 'xb', 'r')):
                bad.append(f'{node.lineno}:open mode')
        if isinstance(fn, ast.Attribute) and fn.attr == 'open' and isinstance(fn.value, ast.Name) and fn.value.id == 'os' \
                and len(node.args) > 1:
            flags = {n.attr for n in ast.walk(node.args[1]) if isinstance(n, ast.Attribute)}
            if 'O_CREAT' in flags and ('O_EXCL' not in flags or flags & {'O_TRUNC', 'O_APPEND'}):
                bad.append(f'{node.lineno}:os.open flags')
    return bad


def helper_tree(fname, func):
    tree = ast.parse(read(os.path.join(PROBES, fname)).decode('utf-8'))
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == func)


def t_static():
    """V25 (REL98 L-01): в фикстурах B11 нет удаления, переименования и перезаписи — разбор исходников, без запуска."""
    found = {}
    for n in ('test_zprobe_release_b11.py', 'test_zprobe_r2_b11.py'):
        tree = ast.parse(read(os.path.join(PROBES, n)).decode('utf-8'))
        found[n] = forbidden_calls(tree)
    for fname, func in (('test_zprobe_r2.py', 'mk'), ('test_zprobe_export.py', 'put0600')):
        found[f'{fname}:{func}'] = forbidden_calls(helper_tree(fname, func), strict_open=False)
    probe = ast.parse("os.rename('a','b')\nshutil.rmtree('x')\nopen('p','wb')\nopen('p','ab')\n"
                      "os.open('p', os.O_WRONLY | os.O_CREAT, 0o600)\n'x'.replace('a','b')\nopen('p','xb')\n")
    self_check = forbidden_calls(probe) == ['1:os.rename', '2:shutil.rmtree', '3:open mode', '4:open mode',
                                            '5:os.open flags']
    case('V25_static_no_delete_rename_overwrite_in_b11_fixtures', self_check and all(v == [] for v in found.values()),
         (self_check, {k: v for k, v in found.items() if v}))


def t_root_install(pkg):
    """Linux root: настоящий проход создания целей (план B9-порядка + REL.apply) в папке испытания."""
    names = ('V20_install_creates_only_b11_folder_and_journal', 'V21_installed_list_check_ok',
             'V22_second_plan_creates_nothing', 'V23_changed_installed_file_flagged',
             'V24_foreign_file_in_target_path_is_conflict_not_overwritten')
    if not ROOT:
        for n in names:
            skip(n, 'needs Linux root')
        return
    base = tmp()
    os.chmod(base, 0o755)
    for d in ('lib', 'sd', 'j'):
        os.mkdir(os.path.join(base, d), 0o755 if d != 'j' else 0o700)
    keep = (M.LIB, REL.JOURNAL_DIR)
    set_lib(os.path.join(base, 'lib', 'probes-b11'))
    REL.JOURNAL_DIR = os.path.join(base, 'j')
    try:
        tg = M.targets(pkg)
        before = sorted(os.listdir(os.path.join(base, 'lib')))
        acts, probs = B9.plan(pkg)
        done = []
        j = REL.Journal('20261117T000000Z')
        try:
            REL.apply(acts, done, j)
            M.sync_dirs(tg)
        finally:
            j.close()
        p = M.installed_path()
        st = os.lstat(p)
        outside = sorted(os.listdir(os.path.join(base, 'lib'))) + sorted(os.listdir(os.path.join(base, 'sd')))
        case(names[0], not probs and len(done) == len(tg) and before == [] and outside == ['probes-b11']
             and stat.S_ISREG(st.st_mode) and (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) == (0, 0, 0o644)
             and read(p) == tg[-1][1] and sorted(os.listdir(M.LIB)) == sorted(os.path.basename(x) for x, _, _ in tg[1:])
             and all(n.startswith('zprobe-install-3.5.5-b11-') for n in os.listdir(os.path.join(base, 'j'))),
             (probs, outside, done[-2:]))
        pr = M.installed_problems(pkg)
        case(names[1], pr == [], pr)
        snap = {n: (os.lstat(os.path.join(M.LIB, n)).st_ino, read(os.path.join(M.LIB, n))) for n in os.listdir(M.LIB)}
        acts2, probs2 = B9.plan(pkg)
        case(names[2], acts2 == [] and probs2 == [] and snap == {
            n: (os.lstat(os.path.join(M.LIB, n)).st_ino, read(os.path.join(M.LIB, n))) for n in os.listdir(M.LIB)},
             (acts2[:2], probs2[:2]))
        # REL98 L-01: подмена — в новой копии папки B11 (без zprobe_r2.py и списка), файлы в ней только создаются
        os.mkdir(os.path.join(base, 'chg'), 0o755)
        lib_c = os.path.join(base, 'chg', 'probes-b11')
        shutil.copytree(M.LIB, lib_c, ignore=shutil.ignore_patterns('zprobe_r2.py', M.INSTALLED_NAME))
        tp = os.path.join(lib_c, 'zprobe_r2.py')
        put(tp, read(os.path.join(M.LIB, 'zprobe_r2.py')) + b'# changed\n')
        set_lib(lib_c)
        put(M.installed_path(), M.targets(pkg)[-1][1])      # список, ожидаемый для этой папки
        pr2 = M.installed_problems(pkg)
        case(names[3], pr2 == [f'{tp} differs from {M.INSTALLED_NAME}'], pr2)
        # чужая цель: файл с другими байтами по пути цели — конфликт, байты не меняются
        base2 = tmp()
        os.chmod(base2, 0o755)
        os.mkdir(os.path.join(base2, 'j'), 0o700)
        set_lib(os.path.join(base2, 'probes-b11'))
        os.mkdir(M.LIB, 0o755)
        foreign = os.path.join(M.LIB, 'zprobe_checks.py')
        put(foreign, b'foreign\n')
        REL.JOURNAL_DIR = os.path.join(base2, 'j')
        acts3, probs3 = B9.plan(pkg)
        case(names[4], probs3 and read(foreign) == b'foreign\n', (acts3[:1], probs3[:2]))
    finally:
        set_lib(keep[0])
        REL.JOURNAL_DIR = keep[1]


def main():
    t_names()
    pkg = t_targets()
    t_pkg_modules()
    t_b10_expected()
    t_b10_check()
    t_builder()
    t_code()
    t_static()
    t_root_install(pkg)
    res = 'FAIL' if not OK else ('PASS_NO_ROOT' if SKIPPED else 'PASS')
    print(f'ZPROBE_RELEASE_B11_TEST={res}')
    return 0 if OK else 1


if __name__ == '__main__':
    sys.exit(main())
