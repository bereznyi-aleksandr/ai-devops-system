#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_release_b15.py
# ВЕРСИЯ: v0.1 (выпуск B15)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-19 14:47 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 14:47 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминал zavod (пускатель); автор, принять не может. Аудитор — ChatGPT.
# НАЗНАЧЕНИЕ: проверки установщика B15 (zprobe_release_b15.py) и сборщика B15 (build_release_3_5_5_b15.py); получен из
#   test_zprobe_release_b14.py v0.1 сдвигом «B13 цел» → «B14 цел» и B14 → B15, те же случаи W01–W53 и новые W54–W57.
#   Отличия: «B14 цел» — папка probes-b14 (14 файлов, права выпуска B14) и две службы -b14@; список INSTALLED B14 из
#   отпечатков равен списку установщика B14 на настоящих байтах выпуска B14 (3a0f20680), 15 строк; в подставном корне
#   B13 — условная старая папка, внешние проверки B8–B13 подставлены, B14 — настоящая; папка B15 — 16 файлов (14 программ:
#   +zprobe_start_status.py, +zprobe_recstore.py), INSTALLED — 17 строк; отметки и журнал — после pb1trial4 (четыре серии,
#   segments=4, seq=62, якорь 305e4933…ba51 / 32273318…5d38); модули «без изменений» — четыре, изменённых и новых — десять;
#   имена b14, b13 и b10 вне комментариев запрещены без исключений; W54–W57 — строка STARTREC (папка startrec: нет —
#   OK, обычная папка root:zprobe 0750 — OK, файл или другие права — FAIL). Без root — чистые функции; под root (в CI —
#   sudo) — настоящий install() и оболочка .sh.
#   Строки: CASE <Wnn_имя> PASS|FAIL|SKIP. Итог: ZPROBE_RELEASE_B15_TEST=PASS | PASS_NO_ROOT | FAIL.
# ОГРАНИЧЕНИЯ: пишет только в новые временные папки (ZPROBE_TEST_ROOT, если задан); ничего не удаляет, не переименовывает
#   и не перезаписывает (put — режим 'xb'; каждый отрицательный случай — своё новое дерево).
import ast
import contextlib
import hashlib
import io
import os
import posixpath
import shutil
import stat
import subprocess
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
import zprobe_release_b15 as M  # noqa: E402
import build_release_3_5_5_b15 as BB  # noqa: E402

B14, B13, B12, B11, B10, B9, REL = M.B14, M.B13, M.B12, M.B11, M.B10, M.B9, M.REL
OK, SKIPPED = True, 0
PROBES = os.path.join(REPO, 'zavod', 'ops', 'server', 'probes')
UNIT_NAMES = M.UNITS
NEW_PROGRAMS = ('zprobe_start_status.py', 'zprobe_recstore.py')   # новые модули B15
_GIT = {}


def case(name, cond, detail=''):
    global OK
    OK &= bool(cond)
    print('CASE', name, 'PASS' if cond else 'FAIL ' + f'-> {detail}'[:300], flush=True)


def skip(name, why='needs Linux'):
    global SKIPPED
    SKIPPED += 1
    print('CASE', name, f'SKIP ({why})', flush=True)


def tmp():
    return tempfile.mkdtemp(prefix='zrel15-', dir=os.environ.get('ZPROBE_TEST_ROOT') or None)


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


def b14_bytes(n):
    """Настоящие байты файла B14: git show в коммите выпуска B14 (3a0f20680; в CI — fetch-depth 0)."""
    if n not in _GIT:
        p = subprocess.run(['git', '-C', REPO, 'show', f'{M.B14_RELEASE_COMMIT}:zavod/ops/server/probes/{n}'],
                           capture_output=True)
        if p.returncode != 0:
            raise RuntimeError(f'git show {n} in the B14 release commit failed: {p.stderr[:120]!r}')
        _GIT[n] = p.stdout
    return _GIT[n]


def fake_pkg(over=None, skip=()):
    """Пакет B15 в новой папке испытания: 12 программ и 2 службы из дерева, RELEASE, пять файлов отпечатков из дерева.
    over — {имя или путь отпечатков: байты} (файл сразу с другими байтами), skip — что не создавать."""
    over = over or {}
    pkg = tmp()
    src = os.path.join(pkg, 'zavod', 'ops', 'server', 'probes')
    for n in M.PROGRAMS + M.UNITS:
        if n not in skip:
            put(os.path.join(src, n), over.get(n, read(os.path.join(PROBES, n))))
    put(os.path.join(pkg, 'RELEASE'), b'commit=' + b'b' * 40 + b'\nversion=3.5.5-b15\n')
    for rel in M.PINS_FILE_SHA:
        if rel not in skip:
            put(os.path.join(pkg, rel), over.get(rel, read(os.path.join(REPO, rel))))
    return pkg


def fake_b14_pkg():
    """Пакет B14 из настоящих байтов B14 (для установщика B14): программы, службы, RELEASE коммита B14, отпечатки B14."""
    pkg = tmp()
    src = os.path.join(pkg, 'zavod', 'ops', 'server', 'probes')
    for n in tuple(B14.LIB_FILES) + B14.UNITS:
        put(os.path.join(src, n), b14_bytes(n))
    put(os.path.join(pkg, 'RELEASE'), f'commit={M.B14_RELEASE_COMMIT}\nversion=3.5.5-b14\n'.encode('ascii'))
    put(os.path.join(pkg, M.PINS_B14_SRC), read(os.path.join(REPO, M.PINS_B14_SRC)))
    return pkg


def fake_b14(lib, pkg, over=None, modes=None, skip=(), dir_mode=0o755, unit_dir=None):
    """Настоящее дерево B14 в новой папке lib (байты B14, список INSTALLED из отпечатков) и две службы -b14@ в unit_dir
    (по умолчанию B14.UNIT_DIR). over — {имя: функция(байты) → байты}: файл сразу с другими байтами; modes — {имя: права};
    skip — каких файлов нет с самого начала. B14.LIB и B14.UNIT_DIR должны указывать на lib и unit_dir: по ним строится
    список INSTALLED."""
    over, modes = over or {}, modes or {}
    unit_dir = unit_dir or B14.UNIT_DIR
    pins = M.pins14(pkg)
    lst, rel = M.b14_installed_expected(pins)
    files = {n: b14_bytes(n) for n in B14.LIB_FILES}
    files.update({'RELEASE': rel, M.INSTALLED_NAME: lst})
    os.mkdir(lib)
    for n, b in files.items():
        if n not in skip:
            put(os.path.join(lib, n), over[n](b) if n in over else b, modes.get(n, B14.LIB_FILES.get(n, 0o644)))
    os.chmod(lib, dir_mode)
    os.makedirs(unit_dir, exist_ok=True)
    for u in B14.UNITS:
        if u not in skip:
            put(os.path.join(unit_dir, u), over[u](b14_bytes(u)) if u in over else b14_bytes(u), modes.get(u, 0o644))
    return lib


def set_paths(lib, unit_dir=None):
    M.LIB = lib
    REL.LIB = lib
    B9.LIB = lib
    if unit_dir is not None:
        M.UNIT_DIR = unit_dir
        B9.UNIT_DIR = unit_dir


def t_names():
    case('W01_lib_units_and_names_b15', M.LIB == '/usr/local/lib/zavod/probes-b15' and REL.LIB == M.LIB and B9.LIB == M.LIB
         and REL.JOURNAL_PREFIX == 'zprobe-install-3.5.5-b15-' and REL.TESTS == '/var/lib/zavod/probes-tests-b15'
         and M.UNITS == ('zprobe-run-b15@.service', 'zprobe-journal-b15@.service') and B9.UNITS == M.UNITS
         and B9.targets is M.targets and B9.unit_expect is M.unit_expect and B9.UNIT_SHOW == M.UNIT_SHOW
         and set(M.UNIT_SHOW) == {'zprobe-journal-b15@check.service', 'zprobe-run-b15@check.service'}
         and M.INSTALLED_NAME == 'INSTALLED.sha256' and M.UNIT_DIR == '/etc/systemd/system'
         and B14.LIB == '/usr/local/lib/zavod/probes-b14' and B11.LIB == '/usr/local/lib/zavod/probes-b11'
         and B10.LIB == '/usr/local/lib/zavod/probes-b10' and B10.B9_LIB == '/usr/local/lib/zavod/probes-b9'
         and all(u in B9.WATCH_UNITS for u in ('zprobe-run-b15@*', 'zprobe-journal-b15@*', 'zprobe-run-b10@*')),
         (M.LIB, REL.LIB, REL.JOURNAL_PREFIX))
    case('W02_programs_are_the_b14_set_and_two_new_modules', set(M.PROGRAMS) == set(B14.PROGRAMS) | set(NEW_PROGRAMS)
         and set(B14.PROGRAMS) == set(B10.LIB_FILES) - {'zprobe_r2.py'} and not set(NEW_PROGRAMS) & set(B14.PROGRAMS)
         and len(M.PROGRAMS) == len(set(M.PROGRAMS)) == 14 and 'zprobe_r2.py' not in M.LIB_FILES
         and all(M.LIB_FILES[n] == B14.LIB_FILES[n] for n in B14.PROGRAMS) and M.LIB_FILES['zprobe-start'] == 0o755
         and all(M.LIB_FILES[n] == 0o644 for n in NEW_PROGRAMS)
         and set(M.UNCHANGED) <= set(M.PROGRAMS) and set(M.ACCEPTED_SHA) | set(M.UNCHANGED) == set(M.PROGRAMS)
         and not set(M.ACCEPTED_SHA) & set(M.UNCHANGED) and set(M.UNIT_ACCEPTED_SHA) == set(M.UNITS),
         sorted(set(M.PROGRAMS) ^ (set(B14.PROGRAMS) | set(NEW_PROGRAMS))))


def t_targets():
    pkg = fake_pkg()
    tg = M.targets(pkg)
    paths = [p for p, _, _ in tg]
    lib, ud = M.LIB, M.UNIT_DIR
    children = {os.path.join(lib, n) for n in M.PROGRAMS} | {os.path.join(lib, n) for n in ('RELEASE', M.INSTALLED_NAME)}
    units = {os.path.join(ud, u) for u in M.UNITS}
    modes = {p: m for p, _, m in tg}
    data = dict((p, d) for p, d, _ in tg)
    inlib = [p for p in paths if os.path.dirname(p) == lib]
    case('W03_targets_b15_only_probes_b15_and_two_units', tg[0] == (lib, None, 0o755)
         and paths[-1] == os.path.join(lib, 'INSTALLED.sha256') and set(paths) == {lib} | children | units
         and len(paths) == 19 and len(inlib) == len(children) == 16
         and all(modes[p] == 0o644 for p in units) and modes[os.path.join(lib, 'zprobe-start')] == 0o755
         and all(modes[p] == 0o644 for p in children if not p.endswith('zprobe-start'))
         and os.path.join(lib, 'zprobe_pins_b9.txt') not in paths and os.path.join(lib, 'zprobe_r2.py') not in paths
         and all(p == lib or p.startswith(lib + '/') or p in units for p in paths)
         and all(data[os.path.join(ud, u)] == read(os.path.join(PROBES, u)) for u in M.UNITS)
         and data[os.path.join(lib, 'RELEASE')] == read(os.path.join(pkg, 'RELEASE'))
         and all(data[os.path.join(lib, n)] == read(os.path.join(PROBES, n)) for n in M.PROGRAMS),
         sorted(set(paths) ^ ({lib} | children | units)))
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
    tp = M.template_path()
    case('W04_installed_list_format_17_rows_with_template_line', fmt_ok and order == sorted(order)
         and len(order) == len(set(order)) == 17 and got == {p: sha(d) for p, d in files.items()}
         and paths[-1] not in got and order.count(tp) == 1 and tp == '/etc/systemd/system/zprobe-run-b15@.service'
         and all('b10' not in p and 'b9' not in p and 'b14' not in p for p in order), text[:200])
    return pkg


def t_pkg_modules():
    p0 = M.pkg_problems(fake_pkg())
    run = read(os.path.join(PROBES, 'zprobe_runner.py')) + b'# x\n'
    seal = read(os.path.join(PROBES, 'zprobe_seal.py')) + b'# x\n'
    unit = read(os.path.join(PROBES, M.UNITS[0])) + b'# x\n'
    p1 = M.pkg_problems(fake_pkg({'zprobe_runner.py': run}))
    p2 = M.pkg_problems(fake_pkg({'zprobe_seal.py': seal}))
    p3 = M.pkg_problems(fake_pkg({M.UNITS[0]: unit}))
    p4 = M.pkg_problems(fake_pkg(skip=('zprobe_dropin.py',)))
    p5 = M.pkg_problems(fake_pkg(skip=(M.PINS_B14_SRC,)))
    p6 = M.pkg_problems(fake_pkg({B13.PINS_B10_SRC: read(os.path.join(REPO, B13.PINS_B10_SRC)) + b'# x\n'}))
    p7 = M.pkg_problems(fake_pkg({'zprobe-start': read(os.path.join(PROBES, 'zprobe-start')) + b'# x\n'}))
    case('W05_package_unchanged_equal_pins_changed_and_units_equal_accepted_sums', p0 == []
         and p1 == ['package zprobe_runner.py differs from the accepted sum']
         and p2 == ['package zprobe_seal.py differs from B14 pins']
         and p3 == [f'package {M.UNITS[0]} differs from the accepted sum']
         and len(p4) == 1 and 'zprobe_dropin.py' in p4[0] and len(p5) == 1 and 'zprobe_pins_b14.txt' in p5[0]
         and p6 == [f'package {B13.PINS_B10_SRC} differs from the known B8-B14 release sum']
         and p7 == ['package zprobe-start differs from the accepted sum'], (p0, p1, p2, p3, p4, p5, p6, p7))
    real = read(os.path.join(REPO, M.PINS_B14_SRC))
    other = real.replace(M.B14_RELEASE_COMMIT.encode(), b'a' * 40)
    pk = fake_pkg({M.PINS_B14_SRC: other})
    try:
        M.pins14(pk)
        refused = ''
    except REL.Refused as x:
        refused = str(x)
    p8 = M.pkg_problems(pk)
    case('W06_known_pins_sums_and_b14_commit', other != real and 'is not B14' in refused
         and p8 == [f'package {M.PINS_B14_SRC} differs from the known B8-B14 release sum']
         and all(sha(read(os.path.join(REPO, r))) == h for r, h in M.PINS_FILE_SHA.items()) and len(M.PINS_FILE_SHA) == 7
         and set(B14.PINS_FILE_SHA) < set(M.PINS_FILE_SHA) and M.B14_RELEASE_COMMIT == '3a0f20680119ed858ce2ee17a865840eab2a63bb'
         and M.PINS_FILE_SHA[M.PINS_B14_SRC] == 'f6da444f8e158dada92243139b9286eb70ca1e9aa4110ddd5414e0aeea36fc40'
         and M.PINS_FILE_SHA[M.PINS_B13_SRC] == '75f15f58683d71e4d37873dda268cb710138cb131e7c188d247f3efc4a665fe9',
         (refused, p8))


def t_b14_expected():
    """Список B14, собранный из отпечатков, равен списку, который строит сам установщик B14 из настоящих байтов B14."""
    pins = M.pins14(fake_pkg())
    lst, rel = M.b14_installed_expected(pins)
    pkg12 = fake_b14_pkg()
    tg12 = B14.targets(pkg12)
    rows = lst.decode('ascii').split('\n')[:-1]
    case('W07_b14_installed_list_rebuilt_equals_b14_installer_list_on_real_b14_bytes', lst == tg12[-1][1] and len(rows) == 15
         and rel == read(os.path.join(pkg12, 'RELEASE')) and all(pins[n] == sha(b14_bytes(n)) for n in B14.LIB_FILES)
         and all(pins[u] == sha(b14_bytes(u)) for u in B14.UNITS)
         and rows == sorted(rows, key=lambda r: r.split('  ', 1)[1]), (sha(lst), sha(tg12[-1][1])))


def t_b14_check():
    names = ('W08_b14_untouched_ok', 'W09_b14_changed_module_flagged', 'W10_b14_extra_file_or_pycache_flagged',
             'W11_b14_release_installed_pins_copy_flagged', 'W12_b14_file_and_folder_mode_flagged',
             'W13_b14_missing_file_or_folder_flagged', 'W41_b14_extra_row_in_installed_list_flagged',
             'W42_b14_second_hard_link_flagged', 'W43_b14_owner_not_root_flagged', 'W44_b14_link_instead_of_file_or_folder_flagged')
    real = set(B9.read_pins_file(os.path.join(REPO, M.PINS_B14_SRC), M.B14_PIN_KEYS))
    case('W14_b14_pin_keys_equal_real_b14_pins', real == set(M.B14_PIN_KEYS) | {'release_commit'} and len(real) == 25
         and len(M.B14_PIN_KEYS) == 24 and set(B14.LIB_FILES) | set(B14.UNITS) < set(M.B14_PIN_KEYS))
    if not UNIX:
        for n in names:
            skip(n)
        return
    keep = (B14.LIB, REL.ROOT_UID, REL.ROOT_GID, B14.UNIT_DIR)
    REL.ROOT_UID, REL.ROOT_GID = os.getuid(), os.getgid()
    pkg = fake_pkg()

    def variant(**kw):
        """Отдельное новое дерево B14: файл сразу с другими байтами, правами или без файла."""
        B14.LIB, B14.UNIT_DIR = os.path.join(tmp(), 'probes-b14'), tmp()
        fake_b14(B14.LIB, pkg, **kw)
        return M.b14_problems(pkg), B14.LIB
    try:
        p0, _l0 = variant()
        case(names[0], p0 == [], p0)
        p1, l1 = variant(over={'zprobe_checks.py': lambda b: b + b'# changed\n'})
        p1b, l1b = variant(over={'zprobe-start': lambda _b: read(os.path.join(PROBES, 'zprobe_checks.py'))})
        case(names[1], p1 == [f'B14 {l1}/zprobe_checks.py differs from B14 pins']
             and p1b == [f'B14 {l1b}/zprobe-start differs from B14 pins'], (p1, p1b))
        _p, la = variant()
        put(os.path.join(la, 'zprobe_extra.py'), b'x\n')
        p2a = M.b14_problems(pkg)
        _p, lb = variant()
        os.mkdir(os.path.join(lb, '__pycache__'))
        p2b = M.b14_problems(pkg)
        case(names[2], len(p2a) == 1 and 'holds other files' in p2a[0] and 'zprobe_extra.py' in p2a[0]
             and len(p2b) == 1 and '__pycache__' in p2b[0], (p2a, p2b))
        bad = {n: variant(over={n: lambda b: b + b'x'})[0] for n in ('RELEASE', M.INSTALLED_NAME, B14.UNITS[0])}
        case(names[3], all(len(v) == 1 and 'differs from B14 pins' in v[0] for v in bad.values()), bad)
        pm, lm = variant(modes={'zprobe_seal.py': 0o666})
        pm2, lm2 = variant(modes={'zprobe_rules.py': 0o664})
        pd, _ld = variant(dir_mode=0o775)
        case(names[4], pm == [f'B14 {lm}/zprobe_seal.py owner or mode differs from the B14 release']
             and pm2 == [f'B14 {lm2}/zprobe_rules.py owner or mode differs from the B14 release']
             and len(pd) == 1 and 'owner or mode' in pd[0], (pm, pm2, pd))
        ps, ls = variant(skip=('zprobe_dropin.py',))
        ps2, ls2 = variant(skip=(M.INSTALLED_NAME,))
        pu, _lu = variant(skip=(B14.UNITS[1],))
        B14.LIB = os.path.join(tmp(), 'none')
        pn = M.b14_problems(pkg)
        case(names[5], ps == [f'B14 {ls}/zprobe_dropin.py FileNotFoundError']
             and ps2 == [f'B14 {ls2}/INSTALLED.sha256 FileNotFoundError']
             and pu == [f'B14 {B14.UNIT_DIR}/{B14.UNITS[1]} FileNotFoundError'] and len(pn) == 1 and 'FileNotFoundError' in pn[0],
             (ps, ps2, pn))
        row = ('0' * 64 + '  ' + '/usr/local/lib/zavod/probes-b14/extra.py\n').encode('ascii')
        pe, le = variant(over={M.INSTALLED_NAME: lambda b: b + row})
        pr, lr = variant(over={M.INSTALLED_NAME: lambda b: b.split(b'\n', 1)[1]})   # недостающая строка — тоже отказ
        case(names[6], pe == [f'B14 {le}/INSTALLED.sha256 differs from B14 pins']
             and pr == [f'B14 {lr}/INSTALLED.sha256 differs from B14 pins'], (pe, pr))
        _p, lh = variant()
        os.link(os.path.join(lh, 'zprobe_seal.py'), os.path.join(tmp(), 'second_name'))
        ph = M.b14_problems(pkg)
        case(names[7], ph == [f'B14 {lh}/zprobe_seal.py is not a plain single-link file'], ph)
        if ROOT:
            _p, lo = variant()
            os.chown(os.path.join(lo, 'zprobe_rules.py'), 65534, 65534)
            po = M.b14_problems(pkg)
            case(names[8], po == [f'B14 {lo}/zprobe_rules.py owner or mode differs from the B14 release'], po)
        else:
            skip(names[8], 'needs Linux root')
        pk, lk = variant(skip=('zprobe_dropin.py',))
        os.symlink(os.path.join(PROBES, 'zprobe_dropin.py'), os.path.join(lk, 'zprobe_dropin.py'))
        pk = M.b14_problems(pkg)
        real_lib = variant()[1]
        link_lib = os.path.join(tmp(), 'probes-b14')
        os.symlink(real_lib, link_lib)
        B14.LIB = link_lib
        pl = M.b14_problems(pkg)
        case(names[9], pk == [f'B14 {lk}/zprobe_dropin.py is not a plain single-link file']
             and pl == [f'B14 {link_lib} is not a plain folder'], (pk, pl))
        B14.LIB, B14.UNIT_DIR = os.path.join(tmp(), 'probes-b14'), tmp()
        fake_b14(B14.LIB, pkg)
        t_common(pkg)
    finally:
        B14.LIB, REL.ROOT_UID, REL.ROOT_GID, B14.UNIT_DIR = keep


STUB_NAMES = ('b8_problems', 'units_problems', 'account_problems', 'journal_problems', 'started_problems')


def stub_env(ns):
    """Подставные внешние проверки (B8, B9, B10, B11, службы, учётная запись, журнал, отметки); возвращает прежние."""
    keep = (B9.b8_problems, B10.b9_problems, B11.b10_problems, B12.b11_problems, B13.b12_problems, B9.units_problems,
            B9.account_problems, B9.journal_problems, B9.started_problems, B10.pycache_problems, B9.parent_problems,
            B14.b13_problems, M.startrec_problems)
    B9.b8_problems, B10.b9_problems, B11.b10_problems, B12.b11_problems, B13.b12_problems = (lambda _p: []), \
        (lambda _p: []), (lambda _p: []), (lambda _p: []), (lambda _p: [])
    B14.b13_problems, M.startrec_problems = (lambda _p: []), (lambda _zp: ([], 'startrec stub'))
    B9.units_problems, B9.account_problems, B9.journal_problems = (lambda: []), (lambda: ([], ns)), (lambda: ([], 'j'))
    B9.started_problems, B10.pycache_problems, B9.parent_problems = (lambda _zp: []), (lambda: ([], [])), (lambda _tg: [])
    return keep


def unstub_env(keep):
    (B9.b8_problems, B10.b9_problems, B11.b10_problems, B12.b11_problems, B13.b12_problems, B9.units_problems,
     B9.account_problems,
     B9.journal_problems, B9.started_problems, B10.pycache_problems, B9.parent_problems,
     B14.b13_problems, M.startrec_problems) = keep


def t_common(pkg):
    """Список проверок: PKG_MODULES, B8, B9, B10, B11, B14, UNITS, ACCOUNT, JOURNAL, STARTED; B14 FAIL виден как FAIL."""
    ns = types.SimpleNamespace(pw_uid=1)
    keep = stub_env(ns)
    try:
        rep = REL.Report()
        zp = M.common(pkg, rep)
        keep_lib = B14.LIB
        keep_ud = B14.UNIT_DIR
        B14.LIB, B14.UNIT_DIR = os.path.join(tmp(), 'probes-b14'), tmp()
        fake_b14(B14.LIB, pkg, skip=('zprobe_seal.py',))
        rep2 = REL.Report()
        try:
            M.common(pkg, rep2)
        finally:
            B14.LIB, B14.UNIT_DIR = keep_lib, keep_ud
        ids = [ln.split()[1] for ln in rep.lines]
        case('W15_common_order_and_b14_fail', zp is ns and ids == ['PKG_MODULES', 'B8', 'B9', 'B10', 'B11', 'B12', 'B13', 'B14',
                                                                   'UNITS', 'ACCOUNT', 'JOURNAL', 'STARTED', 'STARTREC']
             and rep.fails == 0 and rep2.fails == 1 and rep2.lines[7].startswith('CHECK B14 FAIL'), (rep.lines, rep2.lines))
    finally:
        unstub_env(keep)


def t_builder():
    B = BB.B
    P = B.PROBES
    files, keys = set(B.FILES), dict(B.PIN_KEYS)
    chain = ('zprobe_release.py', 'zprobe_release_b9.py', 'zprobe_release_b10.py', 'zprobe_release_b11.py',
             'zprobe_release_b12.py', 'zprobe_release_b13.py', 'zprobe_release_b14.py', 'zprobe_release_b15.py')
    need = {P + n for n in M.PROGRAMS + M.UNITS + chain} | {BB.PHONE_SERIES, BB.PHONE_VERIFY, BB.PHONE_RULES} | {
        'zavod/ops/zprobe_pins_b8.txt', 'zavod/ops/zprobe_pins_b9.txt', 'zavod/ops/zprobe_pins_b10.txt',
        'zavod/ops/zprobe_pins_b11.txt', 'zavod/ops/zprobe_pins_b12.txt', 'zavod/ops/zprobe_pins_b13.txt',
        'zavod/ops/zprobe_pins_b14.txt'}
    missing = sorted(need - files) + sorted(f for f in B.FILES if not os.path.isfile(os.path.join(REPO, f)))
    inst = import_closure('zprobe_release_b15.py')
    consts = BB.PIN_FILES == {k.replace(os.sep, '/'): v for k, v in M.PINS_FILE_SHA.items()} \
        and BB.B14_RELEASE_COMMIT == M.B14_RELEASE_COMMIT and BB.PROGRAMS == M.PROGRAMS and BB.UNITS == M.UNITS \
        and BB.UNCHANGED == M.UNCHANGED and BB.ACCEPTED == M.ACCEPTED_SHA
    case('W16_builder_files_and_constants_equal_installer', not missing and len(B.FILES) == len(files) and need == files
         and inst <= {os.path.basename(f) for f in B.FILES} and consts
         and not any('cell' in f or f.endswith('.sql') or 'ref_b11' in f or f.endswith('zprobe_r2.py') for f in B.FILES),
         (missing, sorted(files ^ need), consts, sorted(inst - {os.path.basename(f) for f in B.FILES})))
    want_keys = set(M.PROGRAMS) | set(M.UNITS) | set(BB.CELL_KEYS) | {'phone_zprobe_series_b15.sh',
                                                                      'phone_zprobe_verify.py', 'phone_zprobe_rules.py',
                                                                      'pc_zprobe_refs.sh', 'pc_zprobe_refs_check.py', 'pc_zprobe_rules.py'}
    case('W17_builder_pin_keys_and_names', set(keys) == want_keys and len(keys) == len(B.PIN_KEYS) == 26
         and all(p in files or p.startswith(BB.CELL) or p.startswith('zavod/ops/pc/') for p in keys.values()) and B.VERSION == '3.5.5-b15'
         and B.PINS_PATH == 'zavod/ops/zprobe_pins_b15.txt' and B.SH_PATH == P + 'zprobe-release-3.5.5-b15.sh'
         and (P + 'zprobe_release_b15.py') in B.EXEC and BB.PHONE_SERIES in B.EXEC and (P + 'zprobe-start') in B.EXEC
         and 'zprobe_release_b15.py" "$M"' in B.SH_TEMPLATE and 'ВЫПУСК: 3.5.5 B15' in B.SH_TEMPLATE
         and 'zprobe_release_b14.py' not in B.SH_TEMPLATE and 'zprobe_release_b11.py' not in B.SH_TEMPLATE
         and 'zprobe_release_b10.py' not in B.SH_TEMPLATE, sorted(set(keys) ^ want_keys))
    tree = lambda p: read(os.path.join(REPO, p))  # noqa: E731
    changed = lambda p: b'# changed\n' if p.endswith('zprobe_seal.py') else tree(p)  # noqa: E731
    other_pins = lambda p: tree(p) + b'# x\n' if p.endswith('zprobe_pins_b14.txt') else tree(p)  # noqa: E731
    old_name = lambda p: tree(p) + b'\nLIB = "/usr/local/lib/zavod/probes-b10"\n' if p.endswith('zprobe_runner.py') else tree(p)  # noqa: E731
    case('W18_builder_refuses_changed_module_pins_file_or_old_names', BB.unchanged_problem(tree) is None
         and 'zprobe_seal.py' in (BB.unchanged_problem(changed) or '') and BB.pins_problem(tree) is None
         and 'zprobe_pins_b14.txt' in (BB.pins_problem(other_pins) or '') and BB.old_names_problem(tree) is None
         and 'probes-b10' in (BB.old_names_problem(old_name) or '') and BB.source_problem(tree) is None
         and BB.source_problem(old_name) is not None)


def b10_names(files):
    """П. 2.3 / (е): прежние имена «probes-b10», «run-b10@», «journal-b10@» вне комментариев — по правилу сборщика."""
    found = []
    for n, data in sorted(files.items()):
        text = data.decode('utf-8')
        for name in BB.OLD_NAMES:
            c = sum(ln.count(name) for ln in text.split('\n') if not ln.lstrip().startswith('#'))
            if c:
                found.append(f'{n}:{name}x{c}')
    return found


def t_names_b10(pkg):
    files = {p.rsplit('/', 1)[-1]: d for p, d, _ in M.targets(pkg) if d is not None and not p.endswith(('RELEASE', 'INSTALLED.sha256'))}
    bad = dict(files)
    bad['zprobe_runner.py'] = files['zprobe_runner.py'] + b'\nX = "/usr/local/lib/zavod/probes-b10/y"\n'
    bad[M.UNITS[1]] = files[M.UNITS[1]] + b'ExecStopPost=/bin/true zprobe-journal-b10@%i\n'
    bad['zprobe_checks.py'] = files['zprobe_checks.py'] + b'\nY = "zprobe-run-b10@"\nZ = "zprobe-run-b10@"\n'
    quiet = dict(files)
    quiet['zprobe_runner.py'] = files['zprobe_runner.py'] + b'\n# probes-b10 only in a comment\n'
    case('W19_installed_files_have_no_old_b10_names_outside_comments', len(files) == 16 and b10_names(files) == []
         and b10_names(quiet) == [] and sorted(b10_names(bad)) == ['zprobe-journal-b15@.service:journal-b10@x1',
                                                                   'zprobe_checks.py:run-b10@x2',
                                                                   'zprobe_runner.py:probes-b10x1'], b10_names(bad))


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




def build_sh():
    """Файл для сервера, собранный настоящим сборщиком B15 из рабочего дерева (объекты git подменены байтами дерева)."""
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
         and text.count('/var/lib/zavod') == 1 and 'zprobe_release_b15.py" "$M" "$P"' in text
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
    base = tempfile.mkdtemp(prefix='zrel15q-', dir='/root')      # 0700 root; все папки Q испытания — внутри неё
    q, q2, q3 = (os.path.join(base, n) for n in ('q', 'q2', 'q3'))
    for d in (q, q2, q3):
        os.mkdir(d, 0o700)
    qlink = os.path.join(base, 'qlink')
    os.symlink(q, qlink)
    q4 = tempfile.mkdtemp(prefix='zrel15q4-', dir='/tmp')       # предок /tmp — запись для всех (1777)
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
    case(names[2], rc == 0 and 'ZPROBE_B15_STAGE=OK' in out and all(w1[k] == v for k, v in w0.items() if k in w1)
         and set(w0) <= set(w1) and new and all(p == pkg_dir or p.startswith(pkg_dir + '/') for p in new)
         and created == sorted([pkg_dir] + [p for p in new if p != pkg_dir]) and f'files={nfiles}' in out,
         (rc, out[-400:], new[:3]))
    rc2, out2 = run('stage')
    case(names[3], rc2 == 0 and 'ZPROBE_B15_STAGE=ALREADY' in out2 and 'CREATED' not in out2 and world(q, shdir) == w1,
         out2[-300:])
    outs = [run(*x) for x in (['preflight'], ['verify-installed'], ['report', 'preflight'], ['report', 'verify-installed'])]

    def read_ok(o, x):
        return 'PACKAGE_DIR=' in o and f'ZPROBE_B15_{x}=' in o and 'CHECK PKG_MODULES OK' in o and 'REPORT=' not in o

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
    w38 = world(q, shdir)
    c38 = [read_ok(rp[1], 'PREFLIGHT'), not any(n.startswith('MARK_') for n in os.listdir(evil)),
           rb[0] == 2, 'BASH_ENV or ENV is set' in rb[1], 'CHECK ' not in rb[1],
           re_[0] == 2, 'BASH_ENV or ENV is set' in re_[1],
           rfn[0] == 2, 'shell functions came from the environment' in rfn[1], w38 == w1]
    case(names[7], all(c38), (c38, rb[0], re_[0], rfn[0], sorted(os.listdir(evil))[:3],
                              sorted(k for k in set(w38) | set(w1) if w38.get(k) != w1.get(k))[:3], rfn[1][-120:]))
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
    case(names[5], rs[0][0] == 1 and 'ZPROBE_B15_STAGE=REFUSED' in rs[0][1] and all(rc == 1 and 'run stage first' in o
                                                                                    for rc, o in rs[1:])
         and world(q, shdir) == w2 and rf[0] == 1 and 'ZPROBE_B15_STAGE=REFUSED' in rf[1] and world(q2, shdir2) == w3,
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

def t_static():
    """W20: в установщике, сборщике и тестах B15 нет удаления, переименования и перезаписи (разбор исходников)."""
    found = {}
    for n in ('zprobe_release_b15.py', 'build_release_3_5_5_b15.py', 'test_zprobe_release_b15.py'):
        found[n] = forbidden_calls(ast.parse(read(os.path.join(PROBES, n)).decode('utf-8')))
    probe = ast.parse("os.rename('a','b')\nshutil.rmtree('x')\nopen('p','wb')\nopen('p','ab')\n"
                      "os.open('p', os.O_WRONLY | os.O_CREAT, 0o600)\n'x'.replace('a','b')\nopen('p','xb')\n")
    self_check = forbidden_calls(probe) == ['1:os.rename', '2:shutil.rmtree', '3:open mode', '4:open mode',
                                            '5:os.open flags']
    case('W20_static_no_delete_rename_overwrite_in_b15', self_check and all(v == [] for v in found.values()),
         (self_check, {k: v for k, v in found.items() if v}))


def t_zprobe_start_static():
    """W53 (з, ж проекта): zprobe-start — пути только b15; ветка --seal-residue состоит из одного отказа и стоит после
    проверки root, до любого Python."""
    st = read(os.path.join(PROBES, 'zprobe-start')).decode('utf-8')
    code = [ln for ln in st.split('\n') if not ln.lstrip().startswith('#')]
    text = '\n'.join(code)
    head = 'if [ "${1:-}" = "--seal-residue" ]; then\n'
    block = st.split(head, 1)[-1].split('\nfi\n', 1)[0]
    body = [ln.strip() for ln in block.split('\n') if ln.strip() and not ln.strip().startswith('#')]
    seal_line = next(i for i, ln in enumerate(code) if ln.startswith('if [ "${1:-}" = "--seal-residue" ]'))
    case('W53_zprobe_start_b15_paths_and_seal_residue_is_only_a_refusal', 'LIB=/usr/local/lib/zavod/probes-b15' in code
         and 'probes-b10' not in text and 'run-b10@' not in text and 'journal-b10@' not in text and 'zprobe_r2' not in text
         and body == ['die "--seal-residue is not part of release B15 (pb1trial2 residue sealed by R2 B12)"']
         and st.count(head) == 1 and seal_line > code.index('[ "$(id -u)" = 0 ] || die "must run as root"')
         and 'systemctl start "zprobe-journal-b15@$S.service"' in text and 'U="zprobe-run-b15@$S.service"' in text
         and 'systemctl start --no-block "$U"' in text
         and text.count('zprobe-run-b15@') == 2 and text.count('zprobe-journal-b15@') == 3
         , (body, seal_line))


def snapshot(d):
    return {n: (os.lstat(os.path.join(d, n)).st_ino, read(os.path.join(d, n))) for n in sorted(os.listdir(d))}


OLD_UNITS = ('zprobe-run@.service', 'zprobe-run-b9@.service', 'zprobe-journal-b9@.service', 'zprobe-run-b10@.service',
             'zprobe-journal-b10@.service', 'zprobe-run-b13@.service', 'zprobe-journal-b13@.service')
OLD_DIRS = ('probes', 'probes-b9', 'probes-b10', 'probes-b11', 'probes-b12', 'probes-b13')


def new_root(pkg, b14_skip=(), b14_over=None):
    """Подставной корень B8–B14: lib (папки probes … probes-b14), sd (службы B8–B10), j (дневники, 0700). Старые папки —
    условные файлы, probes-b14 — настоящие байты B14. Возвращает (base, lib, sd, j)."""
    base = tmp()
    os.chmod(base, 0o755)
    lib, sd, j = (os.path.join(base, n) for n in ('lib', 'sd', 'j'))
    for d_, m_ in ((lib, 0o755), (sd, 0o755), (j, 0o700)):
        os.mkdir(d_)
        os.chmod(d_, m_)
    for d in OLD_DIRS:
        put(os.path.join(lib, d, 'f.py'), (d + '\n').encode())
    keep = (B14.LIB, B14.UNIT_DIR)
    B14.LIB, B14.UNIT_DIR = os.path.join(lib, 'probes-b14'), sd
    try:
        fake_b14(B14.LIB, pkg, skip=b14_skip, over=b14_over, unit_dir=sd)
    finally:
        B14.LIB, B14.UNIT_DIR = keep
    for u in OLD_UNITS:
        put(os.path.join(sd, u), (u + '\n').encode())
    return base, lib, sd, j


def old_snapshot(base):
    """Всё старое в подставном корне: папки lib (кроме probes-b15) и службы sd (кроме *-b15@): тип, права, владелец,
    inode, байты."""
    snap = {}
    lib, sd = os.path.join(base, 'lib'), os.path.join(base, 'sd')

    def one(p):
        st = os.lstat(p)
        snap[p] = (st.st_mode, st.st_uid, st.st_ino, sha(read(p)) if stat.S_ISREG(st.st_mode) else '')
    for top, dirs, files in os.walk(lib):
        if top == lib:
            dirs[:] = [d for d in dirs if d != 'probes-b15']
        for n in sorted(dirs + files):
            one(os.path.join(top, n))
    for n in sorted(os.listdir(sd)):
        if '-b15@' not in n:
            one(os.path.join(sd, n))
    return snap


@contextlib.contextmanager
def paths(lib15, sd, jdir=None, b14lib=None):
    """Пути модулей на подставной корень; прежние значения возвращаются."""
    keep = (M.LIB, M.UNIT_DIR, REL.JOURNAL_DIR, B14.LIB, B14.UNIT_DIR)
    set_paths(lib15, sd)
    if jdir is not None:
        REL.JOURNAL_DIR = jdir
    if b14lib is not None:
        B14.LIB, B14.UNIT_DIR = b14lib, sd
    try:
        yield
    finally:
        set_paths(keep[0], keep[1])
        REL.JOURNAL_DIR, B14.LIB, B14.UNIT_DIR = keep[2], keep[3], keep[4]


def run_mode(fn, pkg, root, cut=None, rc_of=None):
    """Режим установщика в подставном корне; проверки внешней среды (B8–B11, службы, учётная запись, журнал, отметки,
    предки) и systemctl подставлены, проверки пакета и B14 — настоящие. Возвращает (код, вывод, вызовы systemctl)."""
    base, lib, sd, j = root
    calls = []

    def fake_sh(*a):
        calls.append(a)
        return (rc_of or {}).get(a[0], 0), '', ''
    keep = stub_env(types.SimpleNamespace(pw_uid=1))
    keep_sh, keep_apply, keep_show = B9.sh, REL.apply, B9.show_problems
    B9.sh, B9.show_problems = fake_sh, (lambda: [])
    if cut is not None:
        orig = REL.apply

        def cutting(acts, done, jr):
            orig(acts[:cut], done, jr)
            raise OSError('stop injected by the test')
        REL.apply = cutting
    out = io.StringIO()
    um = os.umask(0)
    os.umask(um)            # install ставит umask 077 — после запуска возвращаем прежний
    try:
        with paths(os.path.join(lib, 'probes-b15'), sd, j, os.path.join(lib, 'probes-b14')):
            with contextlib.redirect_stdout(out):
                if fn == 'install':
                    rc = M.install(pkg, REL.Report())
                else:
                    rep = REL.Report()
                    M.preflight(pkg, rep)
                    rc = rep.fails
    finally:
        os.umask(um)
        B9.sh, REL.apply, B9.show_problems = keep_sh, keep_apply, keep_show
        unstub_env(keep)
    return rc, out.getvalue(), calls


def listing14(root):
    base, lib, sd, j = root
    lib15 = os.path.join(lib, 'probes-b15')
    return (sorted(os.listdir(lib15)) if os.path.isdir(lib15) else None), sorted(n for n in os.listdir(sd) if '-b15@' in n)


def t_root_install(pkg):
    """Linux root: настоящий проход создания целей (план B9-порядка + REL.apply) в подставном корне рядом с деревами B8–B14."""
    names = ('W21_install_creates_only_b15_folder_two_units_and_journal', 'W22_installed_list_check_ok',
             'W23_second_plan_creates_nothing', 'W24_interrupted_install_finishes_only_missing_targets',
             'W25_changed_installed_file_flagged', 'W26_foreign_file_in_target_path_is_conflict_not_overwritten',
             'W27_preflight_creates_nothing_and_sees_targets', 'W28_old_trees_untouched_by_install')
    if not ROOT:
        for n in names:
            skip(n, 'needs Linux root')
        return
    root = new_root(pkg)
    base, lib, sd, j = root
    before = old_snapshot(base)
    want14 = sorted(list(M.PROGRAMS) + ['RELEASE', M.INSTALLED_NAME])
    with paths(os.path.join(lib, 'probes-b15'), sd, j, os.path.join(lib, 'probes-b14')):
        tg = M.targets(pkg)
        acts, probs = B9.plan(pkg)
        done = []
        jr = REL.Journal('20261118T000000Z')
        try:
            REL.apply(acts, done, jr)
            M.sync_dirs(tg)
        finally:
            jr.close()
        p = M.installed_path()
        st = os.lstat(p)
        case(names[0], not probs and len(done) == len(tg) == 19 and sorted(os.listdir(M.LIB)) == want14
             and listing14(root)[1] == sorted(M.UNITS) and sorted(os.listdir(sd)) == sorted(OLD_UNITS + B14.UNITS + M.UNITS)
             and sorted(os.listdir(lib)) == sorted(OLD_DIRS + ('probes-b14', 'probes-b15'))
             and stat.S_ISREG(st.st_mode) and (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) == (0, 0, 0o644)
             and read(p) == tg[-1][1] and all(n.startswith('zprobe-install-3.5.5-b15-') for n in os.listdir(j))
             and all(os.lstat(os.path.join(sd, u)).st_mode & 0o777 == 0o644 for u in M.UNITS), (probs, done[-2:]))
        pr = M.installed_problems(pkg)
        case(names[1], pr == [], pr)
        snap = snapshot(M.LIB)
        acts2, probs2 = B9.plan(pkg)
        case(names[2], acts2 == [] and probs2 == [] and snap == snapshot(M.LIB), (acts2[:2], probs2[:2]))
    # обрыв: в новом корне создана только часть целей (первые 4 действия), затем новый план достраивает остальные
    cut = new_root(pkg)
    with paths(os.path.join(cut[1], 'probes-b15'), cut[2], cut[3], os.path.join(cut[1], 'probes-b14')):
        acts3, _ = B9.plan(pkg)
        done3 = []
        jr = REL.Journal('20261118T000001Z')
        try:
            REL.apply(acts3[:4], done3, jr)
        finally:
            jr.close()
        first = snapshot(M.LIB)
        acts4, probs4 = B9.plan(pkg)
        done4 = []
        jr = REL.Journal('20261118T000002Z')
        try:
            REL.apply(acts4, done4, jr)
        finally:
            jr.close()
        kept = all(snapshot(M.LIB)[n] == v for n, v in first.items())
        case(names[3], len(done3) == 4 and not probs4 and len(acts4) == len(tg) - 4 and kept
             and M.installed_problems(pkg) == [], (len(done3), len(acts4), probs4[:2]))
    # подмена — в новой копии папки B15 (без zprobe_runner.py и списка), файлы в ней только создаются
    chg = new_root(pkg)
    lib_c = os.path.join(chg[1], 'probes-b15')
    with paths(os.path.join(lib, 'probes-b15'), sd):
        shutil.copytree(M.LIB, lib_c, ignore=shutil.ignore_patterns('zprobe_runner.py', M.INSTALLED_NAME))
    for u in M.UNITS:
        put(os.path.join(chg[2], u), read(os.path.join(sd, u)))
    tp = os.path.join(lib_c, 'zprobe_runner.py')
    put(tp, read(os.path.join(PROBES, 'zprobe_runner.py')) + b'# changed\n')
    with paths(lib_c, chg[2]):
        put(M.installed_path(), M.targets(pkg)[-1][1])      # список, ожидаемый для этой папки
        pr2 = M.installed_problems(pkg)
    case(names[4], pr2 == [f'{tp} differs from {M.INSTALLED_NAME}'], pr2)
    # чужая цель: файл с другими байтами по пути цели — конфликт, байты не меняются
    fr = new_root(pkg)
    foreign = os.path.join(fr[1], 'probes-b15', 'zprobe_checks.py')
    os.mkdir(os.path.join(fr[1], 'probes-b15'))
    os.chmod(os.path.join(fr[1], 'probes-b15'), 0o755)
    put(foreign, b'foreign\n')
    with paths(os.path.join(fr[1], 'probes-b15'), fr[2], fr[3]):
        acts5, probs5 = B9.plan(pkg)
    case(names[5], probs5 and read(foreign) == b'foreign\n', (acts5[:1], probs5[:2]))
    # preflight (только чтение): на пустом месте TARGETS_ABSENT OK и ничего не создано; на установленном — FAIL
    pre = new_root(pkg)
    b4 = old_snapshot(pre[0])
    top = (sorted(os.listdir(pre[1])), sorted(os.listdir(pre[2])), sorted(os.listdir(pre[3])))
    rc1, out1, calls1 = run_mode('preflight', pkg, pre)
    after = (sorted(os.listdir(pre[1])), sorted(os.listdir(pre[2])), sorted(os.listdir(pre[3])))
    rc2, out2, _c = run_mode('preflight', pkg, root)
    line1 = {ln.split()[1]: ln.split()[2] for ln in out1.split('\n') if ln.startswith('CHECK ')}
    line2 = {ln.split()[1]: ln.split()[2] for ln in out2.split('\n') if ln.startswith('CHECK ')}
    case(names[6], top == after and old_snapshot(pre[0]) == b4 and calls1 == [] and line1.get('TARGETS_ABSENT') == 'OK'
         and line1.get('B14') == 'OK' and line1.get('PKG_MODULES') == 'OK' and rc1 == 0
         and line2.get('TARGETS_ABSENT') == 'FAIL' and rc2 != 0, (out1[-300:], out2[-200:]))
    with paths(os.path.join(lib, 'probes-b15'), sd, j, os.path.join(lib, 'probes-b14')):
        b14_now = M.b14_problems(pkg)
    case(names[7], old_snapshot(base) == before and b14_now == [], (b14_now,))


def t_root_full(pkg):
    """(д) Настоящий install() в подставном корне: 16 файлов и 2 службы, daemon-reload и systemd-analyze verify после файлов,
    старые папки и службы байт в байт те же — при успехе, при сбое посередине и при отказе systemd-analyze; B14 не цел
    или цели B15 уже есть — отказ без записи."""
    names = ('W45_started_series_exactly_pb1trial1_to_pb1trial4', 'W46_existing_b15_targets_refused_nothing_written',
             'W47_install_in_fake_root_16_files_2_units_old_untouched', 'W48_install_cut_midway_stops_keeps_created_old_untouched',
             'W49_systemd_analyze_failure_stops_nothing_removed', 'W50_b14_not_intact_install_refused_nothing_written',
             'W51_installed_files_on_disk_have_no_old_b10_names')
    if not ROOT:
        for n in names:
            skip(n, 'needs Linux root')
        return
    want14 = sorted(list(M.PROGRAMS) + ['RELEASE', M.INSTALLED_NAME])
    # W45 (г): отметки начала — ровно pb1trial1…pb1trial4 (проверка B10: started_problems), лишняя или недостающая — отказ
    keep_data = B9.DATA

    def fake_data(series):
        data = tmp()
        jd, sd_ = os.path.join(data, 'journal'), os.path.join(data, 'started')
        os.mkdir(sd_, 0o750)
        os.chmod(sd_, 0o750)
        for i, (s, ch) in enumerate(series, 1):
            put(os.path.join(jd, f'{i:06d}.jsonl'),
                (B9.J.json.dumps({'kind': 'SERIES_START', 'series': s, 'challenge': ch}) + '\n').encode())
            put(os.path.join(sd_, s), B9.J.marker(s, ch))
        return data
    zp = types.SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid())
    four = (('pb1trial1', 'a1'), ('pb1trial2', 'b2'), ('pb1trial3', 'c3'), ('pb1trial4', 'd4'))
    try:
        B9.DATA = fake_data(four)
        s_ok = B9.started_problems(zp)
        B9.DATA = fake_data(four + (('pb1trial5', 'e5'),))
        s_extra = B9.started_problems(zp)
        B9.DATA = fake_data(four[:3])
        s_less = B9.started_problems(zp)
        B9.DATA = fake_data(four[:3] + (('pb1trial5', 'e5'),))
        s_other = B9.started_problems(zp)
    finally:
        B9.DATA = keep_data
    case(names[0], s_ok == [] and all(len(v) == 1 and 'must hold exactly' in v[0] for v in (s_extra, s_less, s_other))
         and B10.STARTED_SERIES == ('pb1trial1', 'pb1trial2', 'pb1trial3', 'pb1trial4')
         and B9.KNOWN_SERIES == 'pb1trial1,pb1trial2,pb1trial3,pb1trial4' and (B9.EXPECT_SEGMENTS, B9.EXPECT_SEQ) == (4, 62)
         and B9.EXPECT_DIGEST == '305e4933389b5f833a60bef9e421174b365d604534271c0da0f63d28e046ba51'
         and B9.EXPECT_LAST == '32273318589a5ed65074e0aac49aa510653f15c2099432f5f461666d30ec5d38'
         and B9.journal_problems is M.journal_problems and B9.started_problems is B10.started_problems,
         (s_ok, s_extra, s_less, s_other))
    # W46 (г): цели B15 уже есть — отказ без записи (папка probes-b15; чужая служба)
    ra = new_root(pkg)
    foreign_dir = os.path.join(ra[1], 'probes-b15')
    os.mkdir(foreign_dir)
    os.chmod(foreign_dir, 0o755)
    put(os.path.join(foreign_dir, 'zprobe_checks.py'), b'foreign\n')
    ba = old_snapshot(ra[0])
    rca, outa, callsa = run_mode('install', pkg, ra)
    pfa = run_mode('preflight', pkg, ra)
    rb = new_root(pkg)
    put(os.path.join(rb[2], M.UNITS[1]), b'foreign unit\n')
    bb = old_snapshot(rb[0])
    rcb, outb, callsb = run_mode('install', pkg, rb)
    pfb = run_mode('preflight', pkg, rb)
    case(names[1], rca == 1 and 'CONFLICT' in outa and 'nothing created' in outa and callsa == [] and listing14(ra)[1] == []
         and os.listdir(foreign_dir) == ['zprobe_checks.py'] and read(os.path.join(foreign_dir, 'zprobe_checks.py')) == b'foreign\n'
         and os.listdir(ra[3]) == [] and old_snapshot(ra[0]) == ba and 'CHECK TARGETS_ABSENT FAIL' in pfa[1]
         and rcb == 1 and 'CONFLICT' in outb and 'nothing created' in outb and callsb == [] and listing14(rb) == (None, [M.UNITS[1]])
         and read(os.path.join(rb[2], M.UNITS[1])) == b'foreign unit\n' and os.listdir(rb[3]) == []
         and old_snapshot(rb[0]) == bb and 'CHECK TARGETS_ABSENT FAIL' in pfb[1], (outa[-250:], outb[-250:]))
    # W47: настоящий install(): всё создано, systemctl — после файлов, старое то же, повтор — «уже установлено»
    r1 = new_root(pkg)
    b1 = old_snapshot(r1[0])
    rc, out, calls = run_mode('install', pkg, r1)
    lst = listing14(r1)
    rc_again, out_again, calls_again = run_mode('install', pkg, r1)
    lib15 = os.path.join(r1[1], 'probes-b15')
    with paths(lib15, r1[2], r1[3], os.path.join(r1[1], 'probes-b14')):
        disk = {n: read(os.path.join(lib15, n)) for n in os.listdir(lib15)}
        disk.update({u: read(os.path.join(r1[2], u)) for u in M.UNITS})
        problems_disk = M.installed_problems(pkg)
    case(names[2], rc == 0 and 'ZPROBE_B15_INSTALL=OK' in out and lst == (want14, sorted(M.UNITS)) and len(lst[0]) == 16
         and sorted(os.listdir(r1[1])) == sorted(OLD_DIRS + ('probes-b14', 'probes-b15'))
         and sorted(os.listdir(r1[2])) == sorted(OLD_UNITS + B14.UNITS + M.UNITS)
         and calls == [('systemctl', 'daemon-reload'), ('systemd-analyze', 'verify') + M.UNIT_SHOW]
         and 'daemon_reload_rc=0 verify_rc=0' in out and old_snapshot(r1[0]) == b1 and problems_disk == []
         and rc_again == 1 and 'already installed' in out_again and 'nothing created' in out_again and calls_again == []
         and listing14(r1) == lst and len(os.listdir(r1[3])) >= 1
         and all(n.startswith('zprobe-install-3.5.5-b15-') for n in os.listdir(r1[3])), (rc, out[-300:], calls, lst))
    # W48: сбой посередине (после 1, 5, 16 и 18 действий из 19): STOP с перечнем созданного, ничего не удалено, старое то
    # же, systemctl не вызван; повторный install достраивает только недостающее и заканчивается успехом
    ok48, det = True, []
    for k in (1, 5, 16, 18):
        r = new_root(pkg)
        bf = old_snapshot(r[0])
        rc_c, out_c, calls_c = run_mode('install', pkg, r, cut=k)
        lib15 = os.path.join(r[1], 'probes-b15')
        files_c, units_c = listing14(r)
        have = (1 if files_c is not None else 0) + len(files_c or []) + len(units_c)
        first = {n: read(os.path.join(lib15, n)) for n in files_c or []}
        rc_d, out_d, calls_d = run_mode('install', pkg, r)
        kept = all(read(os.path.join(lib15, n)) == v for n, v in first.items())
        good = (rc_c == 1 and 'PARTIAL STOP created=[' in out_c and 'nothing removed' in out_c and calls_c == []
                and have == k and old_snapshot(r[0]) == bf or False)
        good = good and rc_d == 0 and 'ZPROBE_B15_INSTALL=OK' in out_d and listing14(r) == (want14, sorted(M.UNITS)) \
            and kept and old_snapshot(r[0]) == bf and len(calls_d) == 2
        ok48 &= good
        det.append((k, have, rc_c, rc_d))
    case(names[3], ok48, det)
    # W49: systemd-analyze verify вернул ошибку — итог REFUSED, созданное осталось, старое то же
    r3 = new_root(pkg)
    b3 = old_snapshot(r3[0])
    rc3, out3, calls3 = run_mode('install', pkg, r3, rc_of={'systemd-analyze': 1})
    case(names[4], rc3 == 1 and 'verify_rc=1' in out3 and 'ZPROBE_B15_INSTALL=REFUSED' in out3 and 'STOP' in out3
         and listing14(r3) == (want14, sorted(M.UNITS)) and old_snapshot(r3[0]) == b3
         and calls3 == [('systemctl', 'daemon-reload'), ('systemd-analyze', 'verify') + M.UNIT_SHOW], (rc3, out3[-250:], calls3))
    # W50: B14 не цел (нет zprobe_seal.py) — настоящая проверка B14, отказ без записи
    r4 = new_root(pkg, b14_skip=('zprobe_seal.py',))
    b4 = old_snapshot(r4[0])
    rc4, out4, calls4 = run_mode('install', pkg, r4)
    case(names[5], rc4 == 1 and 'CHECK B14 FAIL' in out4 and 'ZPROBE_B15_INSTALL=REFUSED checks fails=1; nothing created' in out4
         and calls4 == [] and listing14(r4) == (None, []) and os.listdir(r4[3]) == [] and old_snapshot(r4[0]) == b4, out4[-300:])
    # W51 (е): установленные на диск файлы — без прежних имён b10 вне комментариев
    files = {n: d for n, d in disk.items() if n not in ('RELEASE', M.INSTALLED_NAME)}
    case(names[6], len(files) == 16 and b10_names(files) == [] and all(
        b'/usr/local/lib/zavod/probes-b15/' in disk[u] for u in M.UNITS), b10_names(files))


def t_startrec():
    """W54–W57: папка записей старта (только чтение): нет — OK; файл или ссылка — FAIL; права или группа не те — FAIL;
    обычная папка root:zprobe 0750 — OK (под root — настоящий chown на root и чужую группу)."""
    names = ('W54_startrec_absent_ok', 'W55_startrec_file_or_link_fail', 'W56_startrec_wrong_mode_or_group_fail',
             'W57_startrec_root_zprobe_0750_folder_ok')
    if not UNIX:
        for n in names:
            skip(n)
        return
    keep = (B9.DATA, REL.ROOT_UID)
    gid = 54321 if ROOT else os.getgid()
    zp = types.SimpleNamespace(pw_uid=1, pw_gid=gid)
    REL.ROOT_UID = 0 if ROOT else os.getuid()

    def data(kind, mode=0o750, group=None):
        d = tmp()
        p = os.path.join(d, M.STARTREC_NAME)
        if kind == 'dir':
            os.mkdir(p)
            if ROOT:
                os.chown(p, 0, gid if group is None else group)
            os.chmod(p, mode)
        elif kind == 'file':
            put(p, b'x\n', 0o750)
        elif kind == 'link':
            os.mkdir(os.path.join(d, 'real'))
            os.symlink(os.path.join(d, 'real'), p)
        B9.DATA = d
        return d
    try:
        data('none')
        p0, l0 = M.startrec_problems(zp)
        case(names[0], p0 == [] and 'absent' in l0, (p0, l0))
        data('file')
        p1, _l = M.startrec_problems(zp)
        data('link')
        p2, _l = M.startrec_problems(zp)
        case(names[1], len(p1) == 1 and 'is not a plain folder' in p1[0] and len(p2) == 1
             and 'is not a plain folder' in p2[0], (p1, p2))
        data('dir', 0o755)
        p3, _l = M.startrec_problems(zp)
        data('dir', 0o770)
        p4, _l = M.startrec_problems(zp)
        if ROOT:
            data('dir', 0o750, group=gid + 1)
            p5, _l = M.startrec_problems(zp)
        else:
            data('dir')
            p5, _l = M.startrec_problems(types.SimpleNamespace(pw_uid=1, pw_gid=gid + 1))
        case(names[2], all(len(v) == 1 and 'owner or mode is not root:zprobe 0750' in v[0] for v in (p3, p4, p5)),
             (p3, p4, p5))
        d6 = data('dir')
        p6, l6 = M.startrec_problems(zp)
        st = os.lstat(os.path.join(d6, M.STARTREC_NAME))
        case(names[3], p6 == [] and l6.endswith('root:zprobe 0750') and stat.S_IMODE(st.st_mode) == 0o750
             and (not ROOT or (st.st_uid, st.st_gid) == (0, gid)), (p6, l6))
    finally:
        B9.DATA, REL.ROOT_UID = keep


def make_stubs(d, marks):
    """Подставные python3, runuser, systemctl, journalctl: при вызове оставляют метку в папке marks и выходят с ошибкой."""
    os.mkdir(d)
    os.mkdir(marks)
    for n in ('python3', 'runuser', 'systemctl', 'journalctl'):
        put(os.path.join(d, n), ('#!/bin/sh\necho ran > "%s/MARK_%s"\nexit 1\n' % (marks, n)).encode(), 0o755)


def t_seal_residue():
    """W52 (з, REL125 L-02): zprobe-start --seal-residue (и любые аргументы) — код 2, строка REFUSED, Python и другие
    программы не запускаются (подставные оставили бы метку), файлы не созданы."""
    name = 'W52_zprobe_start_seal_residue_refused_code_2_python_not_called'
    if not ROOT:
        skip(name, 'needs Linux root')
        return
    d = tmp()
    stub, marks = os.path.join(d, 'stub'), os.path.join(d, 'marks')
    make_stubs(stub, marks)
    ctl_stub, ctl_marks = os.path.join(d, 'stub_ctl'), os.path.join(d, 'marks_ctl')
    make_stubs(ctl_stub, ctl_marks)
    text = read(os.path.join(PROBES, 'zprobe-start'))
    script = os.path.join(d, 'zprobe-start-copy')
    put(script, text.replace(b'/usr/bin/python3', (stub + '/python3').encode()), 0o755)
    ctl = subprocess.run([os.path.join(ctl_stub, 'python3')], capture_output=True)   # контроль: подставная метка работает
    before = {p: (os.lstat(p).st_ino, sha(read(p))) for p in (script, os.path.join(stub, 'python3'))}
    env = {'PATH': stub + ':/usr/bin:/bin'}
    calls = (['--seal-residue', 'pb1trial2'], ['--seal-residue'], ['--seal-residue', 'pb1trial2', 'extra'],
             ['--seal-residue', 'pb1trial1'], ['--seal-residue', ''], ['--seal-residue', '--journal-retry', 'pb1trial2'])
    res = [subprocess.run(['/bin/bash', script] + a, capture_output=True, cwd=d, env=env) for a in calls]
    outs = [r.stdout.decode('utf-8', 'replace') for r in res]
    case(name, ctl.returncode == 1 and os.listdir(ctl_marks) == ['MARK_python3']
         and all(r.returncode == 2 for r in res)
         and all(o.startswith('ZPROBE_START REFUSED: --seal-residue is not part of release B15') for o in outs)
         and os.listdir(marks) == [] and sorted(os.listdir(d)) == ['marks', 'marks_ctl', 'stub', 'stub_ctl', 'zprobe-start-copy']
         and before == {p: (os.lstat(p).st_ino, sha(read(p))) for p in before}, (outs[:2], [r.returncode for r in res]))


def t_accepted():
    """W29: изменённые программы и службы закреплены суммами в установщике; сборщик закрепляет изменённые модули."""
    tree = lambda p: read(os.path.join(REPO, p))  # noqa: E731
    P = BB.B.PROBES
    bad = lambda n: (lambda p: tree(p) + b'# x\n' if p.endswith(n) else tree(p))  # noqa: E731
    p1 = M.pkg_problems(fake_pkg({'zprobe_dropin.py': tree(P + 'zprobe_dropin.py') + b'# x\n'}))
    p2 = M.pkg_problems(fake_pkg({'zprobe_export_rules.py': tree(P + 'zprobe_export_rules.py') + b'# x\n'}))
    p3 = M.pkg_problems(fake_pkg({M.UNITS[1]: tree(P + M.UNITS[1]) + b'# x\n'}))
    keep = BB.B.blob
    BB.B.blob = lambda _r, _c, p: bad('zprobe_checks.py')(p)
    try:
        BB.build(REPO, 'c' * 40)
        refused = ''
    except SystemExit as x:
        refused = str(x)
    finally:
        BB.B.blob = keep
    case('W29_changed_programs_and_units_pinned_to_accepted_sums', BB.ACCEPTED == M.ACCEPTED_SHA
         and set(M.ACCEPTED_SHA) | set(M.UNCHANGED) == set(M.PROGRAMS) and len(M.ACCEPTED_SHA) == 10
         and all(sha(tree(P + n)) == h for n, h in M.ACCEPTED_SHA.items())
         and all(sha(tree(P + u)) == h for u, h in M.UNIT_ACCEPTED_SHA.items())
         and BB.accepted_problem(tree) is None and 'zprobe_checks.py' in (BB.accepted_problem(bad('zprobe_checks.py')) or '')
         and p1 == ['package zprobe_dropin.py differs from B14 pins']
         and p2 == ['package zprobe_export_rules.py differs from B14 pins']
         and p3 == [f'package {M.UNITS[1]} differs from the accepted sum']
         and refused.startswith('RELEASE_REFUSED changed modules differ from the accepted sums'), (p1, p2, p3, refused))


def main():
    t_names()
    pkg = t_targets()
    t_pkg_modules()
    t_b14_expected()
    t_b14_check()
    t_builder()
    t_names_b10(pkg)
    t_static()
    t_zprobe_start_static()
    t_root_install(pkg)
    t_root_full(pkg)
    t_seal_residue()
    t_accepted()
    t_startrec()
    sh = build_sh()
    t_sh_static(sh)
    t_root_sh(sh)
    res = 'FAIL' if not OK else ('PASS_NO_ROOT' if SKIPPED else 'PASS')
    print(f'ZPROBE_RELEASE_B15_TEST={res}')
    return 0 if OK else 1


if __name__ == '__main__':
    sys.exit(main())
