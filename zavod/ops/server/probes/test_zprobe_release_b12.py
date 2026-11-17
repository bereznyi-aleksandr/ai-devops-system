#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_release_b12.py
# ВЕРСИЯ: v0.3 (выпуск B12)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-17 23:50 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-18 01:18 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминальный чат zavod (ad796548; v0.2, v0.3 — чаты-сменщики пускателя)
# v0.3 (REL113 REVISE 0/1/2): папки Q испытаний .sh — внутри новой папки в /root (все предки — root без записи для
#   прочих); W31 — точное число аргументов (пустой второй, лишний третий); W38 — испорченный PATH не используется,
#   BASH_ENV/ENV и функции из окружения — отказ; W39 — после stage Q 0777, предок 0777 или Q-ссылка: все шесть режимов —
#   отказ до Python, ничего не пишется, права вернули — чтение идёт; W40 — Q под /tmp (запись для всех) — отказ.
# v0.2 (REL112 REVISE 0/1/2): W05 — изменённые checks и r2 больше не разрешены (суммы REL111); W29 — закрепка сумм в
#   установщике и сборщике, отказ сборки; W30 — в файле для сервера команды записи только в ветке stage; W31–W37 (Linux
#   root) — настоящая оболочка .sh в папке испытания: неверный вызов, режимы чтения и install без stage — отказ без
#   записей; stage создаёт только новую папку пакета и печатает её перечень; повтор stage ничего не меняет; preflight,
#   verify-installed и report после stage ничего не пишут (report — только stdout, REPORT_SHA256); изменённая или чужая
#   папка пакета — отказ; небезопасная папка Q — отказ. После каждого запуска сверяется дерево Q, папка .sh, /root,
#   /etc/systemd/system, /usr/local/lib/zavod и /var/lib/zavod.
# НАЗНАЧЕНИЕ: проверки установщика B12 (zprobe_release_b12.py) и сборщика B12 (build_release_3_5_5_b12.py), REL111
#   AGREED (B12_RELEASE_BUILD_ALLOWED=YES, Q3), по образцу test_zprobe_release_b11.py. Без root (везде, где есть Linux):
#   пути, состав папки probes-b12 (ровно модули, которые транзитивно импортирует zprobe_r2.py), служб нет, цели и формат
#   INSTALLED.sha256, состав пакета (известные суммы четырёх файлов отпечатков, коммит B11, модули кроме checks и r2 равны
#   отпечаткам B11), список INSTALLED.sha256 B11 пересобирается из настоящих отпечатков и равен списку, который строит
#   сам установщик B11 из настоящих байтов B11 (ref_b11 и дерево), проверка «B11 цел» на настоящих байтах B11 (изменённый
#   файл, лишний файл, __pycache__, RELEASE, INSTALLED, копия отпечатков, права файла и папки, нет файла, нет папки —
#   всё FAIL), порядок списка проверок, сборщик (его суммы равны суммам установщика; отказ при чужом модуле, чужом файле
#   отпечатков и чужом коммите B11), статический запрет удаления, переименования и перезаписи. Только Linux root (в CI —
#   sudo): создание целей настоящим проходом установки в папке испытания рядом с настоящим деревом B11 — повтор ничего не
#   создаёт, обрыв после части целей достраивается только недостающим, подмена файла видна, чужая цель — конфликт без
#   перезаписи, preflight ничего не создаёт, дерево B11 после всего — те же inode и байты.
#   Строки: CASE <Wnn_имя> PASS|FAIL|SKIP. Итог: ZPROBE_RELEASE_B12_TEST=PASS | PASS_NO_ROOT | FAIL.
# ОГРАНИЧЕНИЯ: пишет только в новые временные папки (ZPROBE_TEST_ROOT, если задан); ничего не удаляет, не переименовывает
#   и не перезаписывает (put — режим 'xb'; каждый отрицательный случай — своё новое дерево).
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
import zprobe_release_b12 as M  # noqa: E402
import build_release_3_5_5_b12 as BB  # noqa: E402

B11, B10, B9, REL = M.B11, M.B10, M.B9, M.REL
OK, SKIPPED = True, 0
PROBES = os.path.join(REPO, 'zavod', 'ops', 'server', 'probes')
REF_B11 = {'zprobe_checks.py': os.path.join(PROBES, 'ref_b11', 'zprobe_checks_b11.py.txt'),
           'zprobe_r2.py': os.path.join(PROBES, 'ref_b11', 'zprobe_r2_b11.py.txt')}


def case(name, cond, detail=''):
    global OK
    OK &= bool(cond)
    print('CASE', name, 'PASS' if cond else 'FAIL ' + f'-> {detail}'[:300], flush=True)


def skip(name, why='needs Linux'):
    global SKIPPED
    SKIPPED += 1
    print('CASE', name, f'SKIP ({why})', flush=True)


def tmp():
    return tempfile.mkdtemp(prefix='zrel12-', dir=os.environ.get('ZPROBE_TEST_ROOT') or None)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def read(p):
    with open(p, 'rb') as f:
        return f.read()


def put(p, b, mode=0o644):
    """Только новый файл: режим 'xb' — существующий файл не перезаписывается, а даёт ошибку."""
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


def b11_bytes(n):
    """Настоящие байты модуля B11: checks и r2 — копии ref_b11 (B11 v0.6/v0.8), остальные — дерево (равны B11)."""
    return read(REF_B11[n]) if n in REF_B11 else read(os.path.join(PROBES, n))


def fake_pkg(over=None, skip=()):
    """Пакет B12 в новой папке испытания: модули из дерева, RELEASE, четыре файла отпечатков из дерева. over — {имя модуля
    или путь отпечатков: байты} (файл сразу с другими байтами), skip — что не создавать."""
    over = over or {}
    pkg = tmp()
    src = os.path.join(pkg, 'zavod', 'ops', 'server', 'probes')
    for n in M.LIB_FILES:
        if n not in skip:
            put(os.path.join(src, n), over.get(n, read(os.path.join(PROBES, n))))
    put(os.path.join(pkg, 'RELEASE'), b'commit=' + b'b' * 40 + b'\nversion=3.5.5-b12\n')
    for rel in M.PINS_FILE_SHA:
        if rel not in skip:
            put(os.path.join(pkg, rel), over.get(rel, read(os.path.join(REPO, rel))))
    return pkg


def fake_b11_pkg():
    """Пакет B11 из настоящих байтов B11 (для установщика B11): модули, RELEASE коммита B11, отпечатки B9 и B10."""
    pkg = tmp()
    src = os.path.join(pkg, 'zavod', 'ops', 'server', 'probes')
    for n in B11.LIB_FILES:
        put(os.path.join(src, n), b11_bytes(n))
    put(os.path.join(pkg, 'RELEASE'), f'commit={M.B11_RELEASE_COMMIT}\nversion=3.5.5-b11\n'.encode('ascii'))
    for rel in (M.PINS_B9_SRC, M.PINS_B10_SRC):
        put(os.path.join(pkg, rel), read(os.path.join(REPO, rel)))
    return pkg


def fake_b11(lib, pkg, over=None, modes=None, skip=(), dir_mode=0o755):
    """Настоящее дерево B11 в новой папке lib (байты B11, список INSTALLED из отпечатков). over — {имя: функция(байты) →
    байты}: файл сразу с другими байтами; modes — {имя: права}; skip — каких файлов нет с самого начала."""
    over, modes = over or {}, modes or {}
    pins = M.pins11(pkg)
    lst, rel = M.b11_installed_expected(pins)
    files = {n: b11_bytes(n) for n in B11.LIB_FILES}
    files.update({'RELEASE': rel, M.PINS_B9_NAME: read(os.path.join(REPO, M.PINS_B9_SRC)), M.INSTALLED_NAME: lst})
    os.mkdir(lib)
    for n, b in files.items():
        if n not in skip:
            put(os.path.join(lib, n), over[n](b) if n in over else b, modes.get(n, 0o644))
    os.chmod(lib, dir_mode)
    return lib


def set_lib(lib):
    M.LIB = lib
    REL.LIB = lib


def t_names():
    case('W01_lib_and_no_units_b12', M.LIB == '/usr/local/lib/zavod/probes-b12' and REL.LIB == M.LIB
         and REL.JOURNAL_PREFIX == 'zprobe-install-3.5.5-b12-' and REL.TESTS == '/var/lib/zavod/probes-tests-b12'
         and M.UNITS == () and B9.targets is M.targets and M.INSTALLED_NAME == 'INSTALLED.sha256'
         and B11.LIB == '/usr/local/lib/zavod/probes-b11' and B10.LIB == '/usr/local/lib/zavod/probes-b10'
         and B10.B9_LIB == '/usr/local/lib/zavod/probes-b9', (M.LIB, REL.LIB, REL.JOURNAL_PREFIX))
    closure = import_closure('zprobe_r2.py')
    case('W02_modules_are_exactly_the_imports_of_zprobe_r2', closure == set(M.MODULES) and set(M.LIB_FILES) == closure
         and len(M.MODULES) == len(set(M.MODULES)) == 7 and set(M.CHANGED) == {'zprobe_checks.py', 'zprobe_r2.py'}
         and set(M.MODULES) == set(B11.MODULES) and all(m == 0o644 for m in M.LIB_FILES.values()),
         sorted(closure ^ set(M.MODULES)))


def t_targets():
    pkg = fake_pkg()
    tg = M.targets(pkg)
    paths = [p for p, _, _ in tg]
    lib = M.LIB
    want = {lib} | {os.path.join(lib, n) for n in M.LIB_FILES} | {os.path.join(lib, n) for n in (
        'RELEASE', M.PINS_B9_NAME, M.INSTALLED_NAME)}
    modes = {p: m for p, _, m in tg}
    data = dict((p, d) for p, d, _ in tg)
    case('W03_targets_b12_only_in_probes_b12', tg[0] == (lib, None, 0o755)
         and paths[-1] == os.path.join(lib, 'INSTALLED.sha256') and set(paths) == want and len(paths) == len(want) == 11
         and all(modes[p] == 0o644 for p in paths[1:]) and all(p == lib or p.startswith(lib + '/') for p in paths)
         and data[os.path.join(lib, M.PINS_B9_NAME)] == read(os.path.join(REPO, 'zavod', 'ops', 'zprobe_pins_b9.txt'))
         and data[os.path.join(lib, 'zprobe_checks.py')] == read(os.path.join(PROBES, 'zprobe_checks.py'))
         and data[os.path.join(lib, 'zprobe_r2.py')] == read(os.path.join(PROBES, 'zprobe_r2.py')),
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
    case('W04_installed_list_format', fmt_ok and order == sorted(order) and len(order) == len(set(order)) == 9
         and got == {p: sha(d) for p, d in files.items()} and paths[-1] not in got and 'probes-b11' not in text, text[:200])
    return pkg


def t_pkg_modules():
    p0 = M.pkg_problems(fake_pkg())
    chg = {'zprobe_checks.py': b'# another checks\n', 'zprobe_r2.py': b'# another r2\n'}   # v0.2: уже НЕ разрешены
    p1 = M.pkg_problems(fake_pkg(chg))
    seal_x = read(os.path.join(PROBES, 'zprobe_seal.py')) + b'# x\n'
    p2 = M.pkg_problems(fake_pkg({'zprobe_seal.py': seal_x}))
    p3 = M.pkg_problems(fake_pkg(skip=('zprobe_dropin.py',)))
    p4 = M.pkg_problems(fake_pkg(skip=(M.PINS_B11_SRC,)))
    p5 = M.pkg_problems(fake_pkg({M.PINS_B10_SRC: read(os.path.join(REPO, M.PINS_B10_SRC)) + b'# x\n'}))
    case('W05_package_modules_equal_b11_pins_and_accepted_sums', p0 == []
         and sorted(p1) == [f'package {n} differs from the REL111-accepted sum' for n in sorted(chg)]
         and p2 == ['package zprobe_seal.py differs from B11 pins'] and len(p3) == 1 and 'zprobe_dropin.py' in p3[0]
         and len(p4) == 1 and 'zprobe_pins_b11.txt' in p4[0]
         and p5 == [f'package {M.PINS_B10_SRC} differs from the known B11-release sum'], (p0, p1, p2, p3, p4, p5))
    real = read(os.path.join(REPO, M.PINS_B11_SRC))
    other = real.replace(M.B11_RELEASE_COMMIT.encode(), b'a' * 40)
    pk = fake_pkg({M.PINS_B11_SRC: other})
    try:
        M.pins11(pk)
        refused = ''
    except REL.Refused as x:
        refused = str(x)
    p6 = M.pkg_problems(pk)
    case('W06_known_pins_sums_and_b11_commit', other != real and 'is not B11' in refused
         and p6 == [f'package {M.PINS_B11_SRC} differs from the known B11-release sum']
         and all(sha(read(os.path.join(REPO, r))) == h for r, h in M.PINS_FILE_SHA.items()) and len(M.PINS_FILE_SHA) == 4,
         (refused, p6))


def t_b11_expected():
    """Список B11, собранный из отпечатков, равен списку, который строит сам установщик B11 из настоящих байтов B11."""
    pins = M.pins11(fake_pkg())
    lst, rel = M.b11_installed_expected(pins)
    pkg11 = fake_b11_pkg()
    keep = B9.targets
    B9.targets = B11.targets
    try:
        tg11 = B11.targets(pkg11)
    finally:
        B9.targets = keep
    rows = lst.decode('ascii').split('\n')[:-1]
    case('W07_b11_installed_list_rebuilt_equals_b11_installer_list', lst == tg11[-1][1] and len(rows) == 9
         and rel == read(os.path.join(pkg11, 'RELEASE')) and all(pins[n] == sha(read(p)) for n, p in REF_B11.items())
         and rows == sorted(rows, key=lambda r: r.split('  ', 1)[1]), (sha(lst), sha(tg11[-1][1])))


def t_b11_check():
    names = ('W08_b11_untouched_ok', 'W09_b11_changed_module_flagged', 'W10_b11_extra_file_or_pycache_flagged',
             'W11_b11_release_installed_pins_copy_flagged', 'W12_b11_file_and_folder_mode_flagged',
             'W13_b11_missing_file_or_folder_flagged')
    real = set(B9.read_pins_file(os.path.join(REPO, M.PINS_B11_SRC), M.B11_PIN_KEYS))
    case('W14_b11_pin_keys_equal_real_b11_pins', real == set(M.B11_PIN_KEYS) | {'release_commit'} and len(real) == 9)
    if not UNIX:
        for n in names:
            skip(n)
        return
    keep = (B11.LIB, REL.ROOT_UID, REL.ROOT_GID)
    REL.ROOT_UID, REL.ROOT_GID = os.getuid(), os.getgid()
    pkg = fake_pkg()

    def variant(**kw):
        """Отдельное новое дерево B11: файл сразу с другими байтами, правами или без файла."""
        B11.LIB = os.path.join(tmp(), 'probes-b11')
        fake_b11(B11.LIB, pkg, **kw)
        return M.b11_problems(pkg), B11.LIB
    try:
        p0, _l0 = variant()
        case(names[0], p0 == [], p0)
        p1, l1 = variant(over={'zprobe_checks.py': lambda b: b + b'# changed\n'})
        p1b, l1b = variant(over={'zprobe_r2.py': lambda _b: read(os.path.join(PROBES, 'zprobe_r2.py'))})   # B12 вместо B11
        case(names[1], p1 == [f'B11 {l1}/zprobe_checks.py differs from B11 pins']
             and p1b == [f'B11 {l1b}/zprobe_r2.py differs from B11 pins'], (p1, p1b))
        _p, la = variant()
        put(os.path.join(la, 'zprobe_extra.py'), b'x\n')
        p2a = M.b11_problems(pkg)
        _p, lb = variant()
        os.chmod(lb, 0o755)
        os.mkdir(os.path.join(lb, '__pycache__'))
        p2b = M.b11_problems(pkg)
        case(names[2], len(p2a) == 1 and 'holds other files' in p2a[0] and 'zprobe_extra.py' in p2a[0]
             and len(p2b) == 1 and '__pycache__' in p2b[0], (p2a, p2b))
        bad = {n: variant(over={n: lambda b: b + b'x'})[0] for n in ('RELEASE', M.INSTALLED_NAME, M.PINS_B9_NAME)}
        case(names[3], all(len(v) == 1 and 'differs from B11 pins' in v[0] for v in bad.values()), bad)
        pm, lm = variant(modes={'zprobe_seal.py': 0o666})
        pd, _ld = variant(dir_mode=0o775)
        case(names[4], pm == [f'B11 {lm}/zprobe_seal.py owner or mode differs from the B11 release']
             and len(pd) == 1 and 'owner or mode' in pd[0], (pm, pd))
        ps, ls = variant(skip=('zprobe_dropin.py',))
        B11.LIB = os.path.join(tmp(), 'none')
        pn = M.b11_problems(pkg)
        case(names[5], ps == [f'B11 {ls}/zprobe_dropin.py FileNotFoundError'] and len(pn) == 1
             and 'FileNotFoundError' in pn[0], (ps, pn))
        B11.LIB = os.path.join(tmp(), 'probes-b11')
        fake_b11(B11.LIB, pkg)
        t_common(pkg)
    finally:
        B11.LIB, REL.ROOT_UID, REL.ROOT_GID = keep


def t_common(pkg):
    """Список проверок: PKG_MODULES, B8, B9, B10, B11, UNITS, ACCOUNT, JOURNAL, STARTED; B11 FAIL виден как FAIL."""
    keep = (B9.b8_problems, B10.b9_problems, B11.b10_problems, B9.units_problems, B9.account_problems,
            B9.journal_problems, B9.started_problems, B10.pycache_problems)
    ns = types.SimpleNamespace(pw_uid=1)
    B9.b8_problems, B10.b9_problems, B11.b10_problems = (lambda _p: []), (lambda _p: []), (lambda _p: [])
    B9.units_problems, B9.account_problems, B9.journal_problems = (lambda: []), (lambda: ([], ns)), (lambda: ([], 'j'))
    B9.started_problems, B10.pycache_problems = (lambda _zp: []), (lambda: ([], []))
    try:
        rep = REL.Report()
        zp = M.common(pkg, rep)
        keep_lib = B11.LIB
        B11.LIB = os.path.join(tmp(), 'probes-b11')
        fake_b11(B11.LIB, pkg, skip=('zprobe_seal.py',))
        rep2 = REL.Report()
        try:
            M.common(pkg, rep2)
        finally:
            B11.LIB = keep_lib
        ids = [ln.split()[1] for ln in rep.lines]
        case('W15_common_order_and_b11_fail', zp is ns and ids == ['PKG_MODULES', 'B8', 'B9', 'B10', 'B11', 'UNITS',
                                                                   'ACCOUNT', 'JOURNAL', 'STARTED']
             and rep.fails == 0 and rep2.fails == 1 and rep2.lines[4].startswith('CHECK B11 FAIL'), (rep.lines, rep2.lines))
    finally:
        (B9.b8_problems, B10.b9_problems, B11.b10_problems, B9.units_problems, B9.account_problems,
         B9.journal_problems, B9.started_problems, B10.pycache_problems) = keep


def t_builder():
    B = BB.B
    P = B.PROBES
    files, keys = set(B.FILES), dict(B.PIN_KEYS)
    need = {P + n for n in M.MODULES} | {P + n for n in ('zprobe_journal.py', 'zprobe_release.py', 'zprobe_release_b9.py',
                                                         'zprobe_release_b10.py', 'zprobe_release_b11.py',
                                                         'zprobe_release_b12.py')} | {
        'zavod/ops/zprobe_pins_b8.txt', 'zavod/ops/zprobe_pins_b9.txt', 'zavod/ops/zprobe_pins_b10.txt',
        'zavod/ops/zprobe_pins_b11.txt'}
    missing = sorted(need - files) + sorted(f for f in B.FILES if not os.path.isfile(os.path.join(REPO, f)))
    inst = import_closure('zprobe_release_b12.py')
    consts = BB.PIN_FILES == {k.replace(os.sep, '/'): v for k, v in M.PINS_FILE_SHA.items()} \
        and BB.B11_RELEASE_COMMIT == M.B11_RELEASE_COMMIT and BB.CHANGED == M.CHANGED and BB.MODULES == M.MODULES \
        and BB.ACCEPTED == M.ACCEPTED_SHA
    case('W16_builder_files_and_constants_equal_installer', not missing and len(B.FILES) == len(files) and need == files
         and inst <= {os.path.basename(f) for f in B.FILES} and consts
         and not any('@' in f or 'cell' in f or f.endswith('.sql') or 'ref_b11' in f for f in B.FILES),
         (missing, sorted(files ^ need), consts))
    want_keys = set(M.MODULES) | {'zprobe_pins_b9.txt'}
    case('W17_builder_pin_keys_and_names', set(keys) == want_keys and len(keys) == len(B.PIN_KEYS) == 8
         and all(p in files for p in keys.values()) and B.VERSION == '3.5.5-b12'
         and B.PINS_PATH == 'zavod/ops/zprobe_pins_b12.txt' and B.SH_PATH == P + 'zprobe-release-3.5.5-b12.sh'
         and (P + 'zprobe_release_b12.py') in B.EXEC and 'zprobe_release_b12.py" "$M"' in B.SH_TEMPLATE
         and 'ВЫПУСК: 3.5.5 B12' in B.SH_TEMPLATE and 'zprobe_release_b11.py' not in B.SH_TEMPLATE
         and 'zprobe_release_b10.py' not in B.SH_TEMPLATE, sorted(set(keys) ^ want_keys))
    tree = lambda p: read(os.path.join(REPO, p))  # noqa: E731
    pins11 = BB.B9B.parse(tree('zavod/ops/zprobe_pins_b11.txt'))
    changed = lambda p: b'# changed\n' if p.endswith('zprobe_seal.py') else tree(p)  # noqa: E731
    other_pins = lambda p: tree(p) + b'# x\n' if p.endswith('zprobe_pins_b10.txt') else tree(p)  # noqa: E731
    case('W18_builder_refuses_changed_module_pins_file_or_b11_commit', BB.unchanged_problem(pins11, tree) is None
         and 'zprobe_seal.py' in (BB.unchanged_problem(pins11, changed) or '')
         and BB.unchanged_problem(pins11, lambda p: b'x' if p.endswith(('zprobe_checks.py', 'zprobe_r2.py'))
                                  else tree(p)) is None
         and BB.unchanged_problem({k: v for k, v in pins11.items() if k != 'zprobe_rules.py'}, tree) is not None
         and BB.pins_problem(tree) is None and 'zprobe_pins_b10.txt' in (BB.pins_problem(other_pins) or ''))


def t_code():
    def code(n):
        return '\n'.join(ln for ln in read(os.path.join(PROBES, n)).decode('utf-8').split('\n')
                         if not ln.lstrip().startswith('#'))
    r2 = code('zprobe_r2.py')
    head = read(os.path.join(PROBES, 'zprobe_checks.py')).decode('utf-8').split('\n')[2]
    import zprobe_r2 as R2
    case('W19_r2_b12_names_and_checks_version_in_proof_tool', 'probes-b10' not in r2 and 'probes-b11' not in r2
         and "'pins_b9': '/usr/local/lib/zavod/probes-b12/zprobe_pins_b9.txt'" in r2 and R2.TOOL == 'zprobe-r2-b12-0.2'
         and R2.TOOL_VERSION == 'zprobe-r2-b12-0.2.checks-0.7' and head.startswith('# ВЕРСИЯ: v0.7')
         and R2.CHECKS_VERSION == 'checks-' + head.split('v', 1)[1].split(' ')[0]
         and R2.PATHS['pins_b9'] == '/usr/local/lib/zavod/probes-b12/zprobe_pins_b9.txt'
         and "'tool_version': TOOL_VERSION" in r2, (head, R2.TOOL_VERSION))


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


def t_static():
    """W20: в установщике, сборщике и тестах B12 нет удаления, переименования и перезаписи (разбор исходников)."""
    found = {}
    for n in ('zprobe_release_b12.py', 'build_release_3_5_5_b12.py', 'test_zprobe_release_b12.py',
              'test_zprobe_r2_b12.py'):
        found[n] = forbidden_calls(ast.parse(read(os.path.join(PROBES, n)).decode('utf-8')))
    probe = ast.parse("os.rename('a','b')\nshutil.rmtree('x')\nopen('p','wb')\nopen('p','ab')\n"
                      "os.open('p', os.O_WRONLY | os.O_CREAT, 0o600)\n'x'.replace('a','b')\nopen('p','xb')\n")
    self_check = forbidden_calls(probe) == ['1:os.rename', '2:shutil.rmtree', '3:open mode', '4:open mode',
                                            '5:os.open flags']
    case('W20_static_no_delete_rename_overwrite_in_b12', self_check and all(v == [] for v in found.values()),
         (self_check, {k: v for k, v in found.items() if v}))


def snapshot(d):
    return {n: (os.lstat(os.path.join(d, n)).st_ino, read(os.path.join(d, n))) for n in sorted(os.listdir(d))}


def t_root_install(pkg):
    """Linux root: настоящий проход создания целей (план B9-порядка + REL.apply) в папке испытания рядом с деревом B11."""
    names = ('W21_install_creates_only_b12_folder_and_journal', 'W22_installed_list_check_ok',
             'W23_second_plan_creates_nothing', 'W24_interrupted_install_finishes_only_missing_targets',
             'W25_changed_installed_file_flagged', 'W26_foreign_file_in_target_path_is_conflict_not_overwritten',
             'W27_preflight_creates_nothing_and_sees_targets', 'W28_b11_tree_untouched_by_install')
    if not ROOT:
        for n in names:
            skip(n, 'needs Linux root')
        return
    base = tmp()
    os.chmod(base, 0o755)
    for d in ('lib', 'j', 'j2', 'b11'):
        os.mkdir(os.path.join(base, d), 0o755 if d in ('lib', 'b11') else 0o700)
    keep = (M.LIB, REL.JOURNAL_DIR, B11.LIB)
    B11.LIB = os.path.join(base, 'b11', 'probes-b11')
    fake_b11(B11.LIB, pkg)
    b11_before = snapshot(B11.LIB)
    set_lib(os.path.join(base, 'lib', 'probes-b12'))
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
        case(names[0], not probs and len(done) == len(tg) and before == []
             and sorted(os.listdir(os.path.join(base, 'lib'))) == ['probes-b12']
             and stat.S_ISREG(st.st_mode) and (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) == (0, 0, 0o644)
             and read(p) == tg[-1][1] and sorted(os.listdir(M.LIB)) == sorted(os.path.basename(x) for x, _, _ in tg[1:])
             and all(n.startswith('zprobe-install-3.5.5-b12-') for n in os.listdir(os.path.join(base, 'j'))),
             (probs, done[-2:]))
        pr = M.installed_problems(pkg)
        case(names[1], pr == [], pr)
        snap = snapshot(M.LIB)
        acts2, probs2 = B9.plan(pkg)
        case(names[2], acts2 == [] and probs2 == [] and snap == snapshot(M.LIB), (acts2[:2], probs2[:2]))
        # обрыв: в новой папке создана только часть целей (первые 4 действия), затем новый план достраивает остальные
        os.mkdir(os.path.join(base, 'cut'), 0o755)
        set_lib(os.path.join(base, 'cut', 'probes-b12'))
        REL.JOURNAL_DIR = os.path.join(base, 'j2')
        acts3, _ = B9.plan(pkg)
        done3 = []
        j = REL.Journal('20261117T000001Z')
        try:
            REL.apply(acts3[:4], done3, j)
        finally:
            j.close()
        first = snapshot(M.LIB)
        acts4, probs4 = B9.plan(pkg)
        done4 = []
        j = REL.Journal('20261117T000002Z')
        try:
            REL.apply(acts4, done4, j)
        finally:
            j.close()
        kept = all(snapshot(M.LIB)[n] == v for n, v in first.items())
        case(names[3], len(done3) == 4 and not probs4 and len(acts4) == len(tg) - 4 and kept
             and M.installed_problems(pkg) == [], (len(done3), len(acts4), probs4[:2]))
        # подмена — в новой копии папки B12 (без zprobe_r2.py и списка), файлы в ней только создаются
        os.mkdir(os.path.join(base, 'chg'), 0o755)
        lib_c = os.path.join(base, 'chg', 'probes-b12')
        set_lib(os.path.join(base, 'lib', 'probes-b12'))
        shutil.copytree(M.LIB, lib_c, ignore=shutil.ignore_patterns('zprobe_r2.py', M.INSTALLED_NAME))
        tp = os.path.join(lib_c, 'zprobe_r2.py')
        put(tp, read(os.path.join(M.LIB, 'zprobe_r2.py')) + b'# changed\n')
        set_lib(lib_c)
        put(M.installed_path(), M.targets(pkg)[-1][1])      # список, ожидаемый для этой папки
        pr2 = M.installed_problems(pkg)
        case(names[4], pr2 == [f'{tp} differs from {M.INSTALLED_NAME}'], pr2)
        # чужая цель: файл с другими байтами по пути цели — конфликт, байты не меняются
        base2 = tmp()
        os.chmod(base2, 0o755)
        os.mkdir(os.path.join(base2, 'j'), 0o700)
        set_lib(os.path.join(base2, 'probes-b12'))
        os.mkdir(M.LIB, 0o755)
        foreign = os.path.join(M.LIB, 'zprobe_checks.py')
        put(foreign, b'foreign\n')
        REL.JOURNAL_DIR = os.path.join(base2, 'j')
        acts5, probs5 = B9.plan(pkg)
        case(names[5], probs5 and read(foreign) == b'foreign\n', (acts5[:1], probs5[:2]))
        # preflight (только чтение): на пустом месте TARGETS_ABSENT OK и ничего не создано; на установленной — FAIL
        stubs = (B9.b8_problems, B10.b9_problems, B11.b10_problems, B9.units_problems, B9.account_problems,
                 B9.journal_problems, B9.started_problems, B10.pycache_problems)
        ns = types.SimpleNamespace(pw_uid=1)
        B9.b8_problems, B10.b9_problems, B11.b10_problems = (lambda _p: []), (lambda _p: []), (lambda _p: [])
        B9.units_problems, B9.account_problems = (lambda: []), (lambda: ([], ns))
        B9.journal_problems, B9.started_problems, B10.pycache_problems = (lambda: ([], 'j')), (lambda _z: []), \
            (lambda: ([], []))
        try:
            base3 = tmp()
            os.chmod(base3, 0o755)
            set_lib(os.path.join(base3, 'probes-b12'))
            r1 = REL.Report()
            M.preflight(pkg, r1)
            empty = os.listdir(base3) == []
            set_lib(os.path.join(base, 'lib', 'probes-b12'))
            r2 = REL.Report()
            M.preflight(pkg, r2)
        finally:
            (B9.b8_problems, B10.b9_problems, B11.b10_problems, B9.units_problems, B9.account_problems,
             B9.journal_problems, B9.started_problems, B10.pycache_problems) = stubs
        line = {ln.split()[1]: ln.split()[2] for ln in r1.lines}
        line2 = {ln.split()[1]: ln.split()[2] for ln in r2.lines}
        case(names[6], empty and line.get('TARGETS_ABSENT') == 'OK' and line.get('B11') == 'OK'
             and line2.get('TARGETS_ABSENT') == 'FAIL', (r1.lines, r2.lines[-2:]))
        case(names[7], snapshot(B11.LIB) == b11_before and M.b11_problems(pkg) == [], M.b11_problems(pkg))
    finally:
        set_lib(keep[0])
        REL.JOURNAL_DIR = keep[1]
        B11.LIB = keep[2]


def t_accepted():
    """W29 (REL112 L-02): два изменённых модуля закреплены суммами REL111 и в установщике, и в сборщике."""
    tree = lambda p: read(os.path.join(REPO, p))  # noqa: E731
    P = BB.B.PROBES
    bad_r2 = lambda p: tree(p) + b'# x\n' if p.endswith('zprobe_r2.py') else tree(p)  # noqa: E731
    bad_ch = lambda p: tree(p) + b'# x\n' if p.endswith('zprobe_checks.py') else tree(p)  # noqa: E731
    p1 = M.pkg_problems(fake_pkg({'zprobe_r2.py': tree(P + 'zprobe_r2.py') + b'# x\n'}))
    p2 = M.pkg_problems(fake_pkg({'zprobe_checks.py': tree(P + 'zprobe_checks.py') + b'# x\n'}))
    keep = BB.B.blob
    BB.B.blob = lambda _r, _c, p: bad_r2(p)
    try:
        BB.build(REPO, 'c' * 40)
        refused = ''
    except SystemExit as x:
        refused = str(x)
    finally:
        BB.B.blob = keep
    case('W29_changed_modules_pinned_to_rel111_sums', BB.ACCEPTED == M.ACCEPTED_SHA and set(M.ACCEPTED_SHA) == set(M.CHANGED)
         and all(sha(tree(P + n)) == h for n, h in M.ACCEPTED_SHA.items())
         and BB.accepted_problem(tree) is None and 'zprobe_r2.py' in (BB.accepted_problem(bad_r2) or '')
         and 'zprobe_checks.py' in (BB.accepted_problem(bad_ch) or '')
         and p1 == ['package zprobe_r2.py differs from the REL111-accepted sum']
         and p2 == ['package zprobe_checks.py differs from the REL111-accepted sum']
         and refused.startswith('RELEASE_REFUSED changed modules differ from the REL111-accepted sums'), (p1, p2, refused))


def build_sh():
    """Файл для сервера, собранный настоящим сборщиком B12 из рабочего дерева (объекты git подменены байтами дерева)."""
    keep = BB.B.blob
    BB.B.blob = lambda _r, _c, p: read(os.path.join(REPO, p))
    try:
        return BB.build(REPO, 'c' * 40)[2]
    finally:
        BB.B.blob = keep


WRITE_CMD = r'(^\s*|[;&{(]\s*|\s\|{1,2}\s*|\bthen\s+|\belse\s+)(mkdir|touch|cp|mv|rm|ln|tee|dd|truncate|chmod|chown|install|tar)\b'


def sh_writes(lines):
    """Строки оболочки с командой записи или перенаправлением в файл (кроме >&2 и 2>&1)."""
    import re
    out = []
    for i, ln in lines:
        code = ln.split(' #', 1)[0] if not ln.lstrip().startswith('#') else ''
        if re.search(WRITE_CMD, code) or re.search(r'(?<![0-9&])>{1,2}\s*(?!&)[^ ]', code.replace('2>&1', '')):
            out.append(i)
    return out


def t_sh_static(sh):
    """W30 (REL112 M-01): в файле для сервера команды записи есть только в ветке stage; exec python — после неё, один."""
    text = sh.split(b'\n__ZPROBE_PKG_BASE64__\n', 1)[0].decode('utf-8')
    lines = list(enumerate(text.split('\n')))
    start = next(i for i, ln in lines if ln == 'if [ "$M" = stage ]; then')
    end = next(i for i, ln in lines if i > start and ln == 'fi')
    w = sh_writes(lines)
    inside = [i for i in w if start < i < end]
    outside = [i for i in w if not start < i < end]
    probe = sh_writes(list(enumerate(['  mkdir -m 0755 "$P"', 'echo x > /tmp/y', 'echo x >&2', 'a 2>&1', '# rm x',
                                      'payload | tar -C "$P" -xf -', 'echo "usage: install"', 'cat f >> g'])))
    execs = [i for i, ln in lines if ln.startswith('exec ')]
    case('W30_sh_writes_only_in_stage_branch', probe == [0, 1, 5, 7] and outside == [] and len(inside) == 2
         and execs == [len(lines) - 1] and execs[0] > end and text.count('\nQ=/var/lib/zavod\n') == 1
         and text.count('/var/lib/zavod') == 1 and 'zprobe_release_b12.py" "$M" "$P"' in text
         and 'REPORT=' not in text, (outside, inside, probe, execs))


def world(q, shdir):
    """Всё, что могла бы задеть оболочка: дерево папки Q (тип, права, размер, inode, mtime, байты), папка файла .sh,
    имена в /root и /etc/systemd/system, есть ли /usr/local/lib/zavod и /var/lib/zavod."""
    snap = {}
    for d in (q, shdir):
        for top, dirs, files in os.walk(d):
            for n in sorted(dirs + files):
                p = os.path.join(top, n)
                st = os.lstat(p)
                snap[p] = (st.st_mode, st.st_size, st.st_ino, st.st_mtime_ns,
                           sha(read(p)) if stat.S_ISREG(st.st_mode) else '')
    for d in ('/root', '/etc/systemd/system'):
        snap[d] = tuple(sorted(os.listdir(d))) if os.path.isdir(d) else None
    for d in ('/usr/local/lib/zavod', '/var/lib/zavod'):
        snap[d] = os.path.lexists(d)
    return snap


def t_root_sh(sh):
    """W31–W40 (REL112 M-01, L-01; REL113 M-01, L-01, L-02): настоящая оболочка .sh под root, папка Q — новая папка
    испытания внутри новой папки в /root (все предки — root, без записи для прочих; подменена ровно одна строка Q=);
    после каждого запуска сверяется всё, что она могла бы записать."""
    import subprocess
    names = ('W31_sh_bad_usage_and_argument_count_refused_nothing_written',
             'W32_sh_read_modes_and_install_without_stage_refused_nothing_written',
             'W33_sh_stage_creates_only_new_package_folder_and_lists_it', 'W34_sh_stage_again_changes_nothing',
             'W35_sh_preflight_verify_report_after_stage_write_nothing', 'W36_sh_changed_or_foreign_package_folder_refused',
             'W37_sh_stage_refuses_unsafe_q_folder', 'W38_sh_spoiled_path_ignored_bash_env_and_functions_refused',
             'W39_sh_q_or_parent_unsafe_or_link_after_stage_refused_before_python',
             'W40_sh_q_under_world_writable_parent_refused')
    if not ROOT:
        for n in names:
            skip(n, 'needs Linux root')
        return
    base = tempfile.mkdtemp(prefix='zrel12q-', dir='/root')      # 0700 root; все папки Q испытания — внутри неё
    q, q2, q3 = (os.path.join(base, n) for n in ('q', 'q2', 'q3'))
    for d in (q, q2, q3):
        os.mkdir(d, 0o700)
    qlink = os.path.join(base, 'qlink')
    os.symlink(q, qlink)
    q4 = tempfile.mkdtemp(prefix='zrel12q4-', dir='/tmp')       # предок /tmp — запись для всех (1777)
    shdir, shdir2, shdir3, shdir4 = tmp(), tmp(), tmp(), tmp()
    a = b'\nQ=/var/lib/zavod\n'

    def sh_for(qd, sd):
        p = os.path.join(sd, 'rel.sh')
        put(p, sh.replace(a, b'\nQ=' + qd.encode() + b'\n'), 0o644)
        return p

    path, path2, path3, path4 = sh_for(q, shdir), sh_for(q2, shdir2), sh_for(q3, shdir3), sh_for(q4, shdir4)
    pathl = os.path.join(shdir, 'rel_link.sh')
    put(pathl, sh.replace(a, b'\nQ=' + qlink.encode() + b'\n'), 0o644)
    evil = os.path.join(shdir, 'evil')                          # подставные программы: оставили бы метку в evil
    os.mkdir(evil, 0o755)
    for n in ('sha256sum', 'find', 'mkdir', 'tar', 'python3', 'stat', 'sed', 'base64', 'dirname', 'cut', 'wc', 'sort'):
        put(os.path.join(evil, n), ('#!/bin/sh\necho ran > "%s/MARK_%s"\nexit 1\n' % (evil, n)).encode(), 0o755)
    benv = os.path.join(shdir, 'bash_env.sh')
    put(benv, b'ZT_BASH_ENV_RAN=1\n', 0o644)
    pkg_dir = os.path.join(q, 'probes-pkg-' + 'c' * 12)

    def run(*args, sh_path=path, env=None):
        p = subprocess.run(['/bin/bash', sh_path] + list(args), capture_output=True, cwd=shdir, env=env)
        return p.returncode, p.stdout.decode('utf-8', 'replace') + p.stderr.decode('utf-8', 'replace')

    w0 = world(q, shdir)
    bad = ([], ['report'], ['preflight', 'x'], ['stage', 'x'], ['report', 'install'], ['bogus'], ['stage', ''],
           ['stage', '', 'x'], ['preflight', ''], ['install', 'x'], ['report', 'preflight', 'x'], ['report', 'preflight', ''],
           ['', 'stage'])
    r = [run(*x) for x in bad]
    case(names[0], sh.count(a) == 1 and all(rc == 2 and 'usage' in o for rc, o in r) and world(q, shdir) == w0
         and not os.path.lexists(pkg_dir), [x for x, (rc, o) in zip(bad, r) if rc != 2][:3])
    r = [run(*x) for x in (['preflight'], ['verify-installed'], ['install'], ['report', 'preflight'],
                           ['report', 'verify-installed'])]
    case(names[1], all(rc == 1 and 'run stage first' in o and 'CHECK ' not in o for rc, o in r)
         and world(q, shdir) == w0 and not os.path.lexists(pkg_dir), r[:2])
    rc, out = run('stage')
    w1 = world(q, shdir)
    new = sorted(set(w1) - set(w0))
    created = sorted(ln.split(' ', 3)[3] for ln in out.split('\n') if ln.startswith('CREATED '))
    nfiles = sum(1 for p in new if stat.S_ISREG(w1[p][0]))
    case(names[2], rc == 0 and 'ZPROBE_B12_STAGE=OK' in out and all(w1[k] == v for k, v in w0.items() if k in w1)
         and set(w0) <= set(w1) and new and all(p == pkg_dir or p.startswith(pkg_dir + '/') for p in new)
         and created == sorted([pkg_dir] + [p for p in new if p != pkg_dir]) and f'files={nfiles}' in out,
         (rc, out[-400:], new[:3]))
    rc2, out2 = run('stage')
    case(names[3], rc2 == 0 and 'ZPROBE_B12_STAGE=ALREADY' in out2 and 'CREATED' not in out2 and world(q, shdir) == w1,
         out2[-300:])
    outs = [run(*x) for x in (['preflight'], ['verify-installed'], ['report', 'preflight'], ['report', 'verify-installed'])]

    def read_ok(o, x):
        return 'PACKAGE_DIR=' in o and f'ZPROBE_B12_{x}=' in o and 'CHECK PKG_MODULES OK' in o and 'REPORT=' not in o

    rep_ok = all(read_ok(o, x) for (_, o), x in zip(outs, ('PREFLIGHT', 'VERIFY_INSTALLED', 'PREFLIGHT', 'VERIFY_INSTALLED')))
    for _, o in outs[2:]:
        checks = [ln for ln in o.split('\n') if ln.startswith('CHECK ')]
        body = ('\n'.join(checks) + '\n').encode('utf-8')
        rep_ok &= f'REPORT_SHA256={sha(body)} ' in o
    case(names[4], rep_ok and 'REPORT_SHA256' not in outs[0][1] and world(q, shdir) == w1,
         [o[-300:] for _, o in outs[:1]])
    # W38: испорченный PATH не используется (подставные программы не запускались, проверка как обычно); BASH_ENV/ENV и
    # функции из окружения — отказ до любых действий
    env0 = {k: v for k, v in os.environ.items() if k not in ('BASH_ENV', 'ENV') and not k.startswith('BASH_FUNC_')}
    rp = run('preflight', env=dict(env0, PATH=evil + ':' + env0.get('PATH', '/usr/bin:/bin')))
    rb = run('preflight', env=dict(env0, BASH_ENV=benv))
    re_ = run('stage', env=dict(env0, ENV=benv))
    rfn = run('preflight', env=dict(env0, **{'BASH_FUNC_mkdir%%': '() { echo evil; }'}))
    case(names[7], read_ok(rp[1], 'PREFLIGHT') and os.listdir(evil) == sorted(os.listdir(evil))
         and not any(n.startswith('MARK_') for n in os.listdir(evil))
         and rb[0] == 2 and 'BASH_ENV or ENV is set' in rb[1] and 'CHECK ' not in rb[1]
         and re_[0] == 2 and 'BASH_ENV or ENV is set' in re_[1]
         and rfn[0] == 2 and 'shell functions came from the environment' in rfn[1] and world(q, shdir) == w1,
         (rp[1][-200:], rb[1][-150:], rfn[1][-150:], os.listdir(evil)))
    # W39: после stage папка Q 0777, предок 0777 или Q — ссылка: все режимы — отказ до Python, ничего не пишется;
    # права вернули — чтение снова идёт
    modes = (['stage'], ['preflight'], ['verify-installed'], ['install'], ['report', 'preflight'],
             ['report', 'verify-installed'])
    refused = []
    for d in (q, base):
        os.chmod(d, 0o777)
        try:
            refused += [run(*m) for m in modes]
        finally:
            os.chmod(d, 0o700)
    refused += [run(*m, sh_path=pathl) for m in modes]
    back = run('preflight')
    case(names[8], len(refused) == 18 and all(rc == 1 and 'is not a root-only plain folder' in o and 'CHECK ' not in o
                                              and 'PACKAGE_DIR=' not in o for rc, o in refused)
         and read_ok(back[1], 'PREFLIGHT') and world(q, shdir) == w1,
         [o[-150:] for rc, o in refused if rc != 1 or 'CHECK ' in o][:2])
    # изменённая папка пакета (лишний файл) — отказ stage и чтения; чужая пустая папка с тем же именем — отказ stage
    put(os.path.join(pkg_dir, 'extra.txt'), b'x\n')
    w2 = world(q, shdir)
    rs = [run('stage'), run('preflight'), run('report', 'preflight')]
    os.mkdir(os.path.join(q2, 'probes-pkg-' + 'c' * 12), 0o755)
    w3 = world(q2, shdir2)
    rf = run('stage', sh_path=path2)
    case(names[5], rs[0][0] == 1 and 'ZPROBE_B12_STAGE=REFUSED' in rs[0][1] and all(rc == 1 and 'run stage first' in o
                                                                                    for rc, o in rs[1:])
         and world(q, shdir) == w2 and rf[0] == 1 and 'ZPROBE_B12_STAGE=REFUSED' in rf[1] and world(q2, shdir2) == w3,
         (rs[0][1][-200:], rf[1][-200:]))
    os.chmod(q3, 0o777)
    w4 = world(q3, shdir3)
    ru = run('stage', sh_path=path3)
    case(names[6], ru[0] == 1 and 'is not a root-only plain folder' in ru[1] and world(q3, shdir3) == w4
         and os.listdir(q3) == [], ru[1][-200:])
    w5 = world(q4, shdir4)
    rt = [run(*m, sh_path=path4) for m in (['stage'], ['preflight'])]
    case(names[9], all(rc == 1 and 'is not a root-only plain folder' in o for rc, o in rt) and world(q4, shdir4) == w5
         and os.listdir(q4) == [] and stat.S_IMODE(os.stat('/tmp').st_mode) & 0o002, [o[-150:] for _, o in rt])


def main():
    t_names()
    pkg = t_targets()
    t_pkg_modules()
    t_b11_expected()
    t_b11_check()
    t_builder()
    t_code()
    t_static()
    t_root_install(pkg)
    t_accepted()
    sh = build_sh()
    t_sh_static(sh)
    t_root_sh(sh)
    res = 'FAIL' if not OK else ('PASS_NO_ROOT' if SKIPPED else 'PASS')
    print(f'ZPROBE_RELEASE_B12_TEST={res}')
    return 0 if OK else 1


if __name__ == '__main__':
    sys.exit(main())
