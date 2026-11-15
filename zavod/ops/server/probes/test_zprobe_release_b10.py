#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_release_b10.py
# ВЕРСИЯ: v0.1 (выпуск B10)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-15 00:18 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-15 00:18 +02:00
# ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · напарник · 04» (869221b9), помощник
# НАЗНАЧЕНИЕ: проверки установщика B10 (zprobe_release_b10.py) и сборщика B10 (build_release_3_5_5_b10.py), проект
#   B10 v0.18 раздел 7 и 1.3 Б. Без root (везде): пути, службы и состав LIB — B10; файлы служб B10 = службы B9 с
#   именами B10; свойства служб для verify-installed — B10; цели и формат INSTALLED.sha256 (по
#   zprobe_unstarted.INSTALLED_LINE / expected_fragment); проверка B9 по отпечаткам B9 (изменённый файл, служба,
#   лишний файл, RELEASE); имя SQL (B9 — 06, B10 — 08); состав сборщика; имена B10 в бегунке, журнале и
#   zprobe-start. Только Linux root (в CI — sudo): создание целей настоящим проходом установки в папке испытания —
#   INSTALLED.sha256 root 0644, список и эталон шаблона, повтор ничего не создаёт, подмена файла видна.
#   Строки: CASE <Nnn_имя> PASS|FAIL|SKIP. Итог: ZPROBE_RELEASE_B10_TEST=PASS | PASS_NO_ROOT | FAIL.
# ОГРАНИЧЕНИЯ: пишет только в новые временные папки (ZPROBE_TEST_ROOT, если задан); ничего не удаляет.
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
    # пути целей — серверные (/usr/local/..., /etc/...): соединяются через «/», как на Linux
    os.path.join = posixpath.join
ROOT = UNIX and os.geteuid() == 0 and sys.platform.startswith('linux')
sys.path.insert(0, HERE)
import zprobe_release_b10 as I  # noqa: E402
import zprobe_unstarted as UN  # noqa: E402
import build_release_3_5_5_b9 as B9B  # noqa: E402  — до сборщика B10: проверка, что B9 по умолчанию 06
B9B_SQL_BEFORE = B9B.SQL
import build_release_3_5_5_b10 as BB  # noqa: E402

B9 = I.B9
REL = I.REL
OK, SKIPPED = True, 0
PROBES = os.path.join(REPO, 'zavod', 'ops', 'server', 'probes')
NEW = ('zprobe_dropin.py', 'zprobe_checks.py', 'zprobe_seal.py', 'zprobe_unstarted.py', 'zprobe_export_rules.py',
       'zprobe_export.py', 'zprobe_r2.py', 'zevidence_send.py')


def case(name, cond, detail=''):
    global OK
    OK &= bool(cond)
    print('CASE', name, 'PASS' if cond else 'FAIL ' + f'-> {detail}'[:300], flush=True)


def skip(name):
    global SKIPPED
    SKIPPED += 1
    print('CASE', name, 'SKIP (needs Linux root)', flush=True)


def tmp():
    return tempfile.mkdtemp(prefix='zrel10-', dir=os.environ.get('ZPROBE_TEST_ROOT') or None)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def read(p):
    with open(p, 'rb') as f:
        return f.read()


def put(p, b, mode=0o644):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'wb') as f:
        f.write(b)
    os.chmod(p, mode)


def code_lines(text):
    return [ln for ln in text.split('\n') if not ln.startswith('#')]


def fake_pkg():
    """Пакет в папке испытания: программы и службы B10 из дерева, RELEASE, отпечатки B9."""
    pkg = tmp()
    src = os.path.join(pkg, 'zavod', 'ops', 'server', 'probes')
    for n in list(I.LIB_FILES) + list(I.UNITS):
        put(os.path.join(src, n), read(os.path.join(PROBES, n)))
    put(os.path.join(pkg, 'RELEASE'), b'commit=' + b'a' * 40 + b'\nversion=3.5.5-b10\n')
    put(os.path.join(pkg, I.PINS_B9_SRC), read(os.path.join(REPO, I.PINS_B9_SRC)))
    return pkg


def set_paths(lib, unit_dir, b9_lib=None):
    I.LIB, I.UNIT_DIR = lib, unit_dir
    if b9_lib is not None:
        I.B9_LIB = b9_lib
    I.sync_paths()


def t_names():
    want = dict(B9.LIB_FILES)
    case('N01_lib_and_units_b10', I.LIB == '/usr/local/lib/zavod/probes-b10' and B9.LIB == I.LIB
         and REL.LIB == I.LIB and REL.JOURNAL_PREFIX == 'zprobe-install-3.5.5-b10-'
         and I.UNITS == ('zprobe-run-b10@.service', 'zprobe-journal-b10@.service') and B9.UNITS == I.UNITS
         and I.UNIT_SHOW == ('zprobe-journal-b10@check.service', 'zprobe-run-b10@check.service')
         and B9.UNIT_SHOW == I.UNIT_SHOW
         and all(u in I.WATCH_UNITS for u in ('zprobe-run@*', 'zprobe-run-b9@*', 'zprobe-journal-b9@*',
                                              'zprobe-run-b10@*', 'zprobe-journal-b10@*', 'zagent@*')),
         (I.LIB, I.UNITS, I.UNIT_SHOW, I.WATCH_UNITS))
    want.update({n: 0o644 for n in NEW})
    case('N02_lib_files_b9_set_plus_new_modules', I.LIB_FILES == want and B9.LIB_FILES == want
         and I.LIB_FILES['zprobe-start'] == 0o755 and set(I.B9_LIB_KEYS) == {'pb1_session.py', 'zprobe_rules.py',
                                                                            'zprobe_runner.py', 'zprobe_journal.py',
                                                                            'zprobe-start'}, I.LIB_FILES)
    bad = []
    for kind in ('run', 'journal'):
        b9 = read(os.path.join(PROBES, f'zprobe-{kind}-b9@.service')).decode('utf-8')
        b10 = read(os.path.join(PROBES, f'zprobe-{kind}-b10@.service')).decode('utf-8')
        conv = (b9.replace('probes-b9', 'probes-b10').replace('zprobe-run-b9@', 'zprobe-run-b10@')
                .replace('zprobe-journal-b9@', 'zprobe-journal-b10@').replace('(release B9)', '(release B10)'))
        if code_lines(conv) != code_lines(b10) or 'b9' in '\n'.join(code_lines(b10)) \
                or '(release B10)' not in b10:
            bad.append(kind)
    case('N03_unit_files_are_b9_text_with_b10_names', not bad, bad)
    ue = I.unit_expect()
    flat = repr({u: {k: v for k, v in w.items() if not callable(v)} for u, w in ue.items()})
    case('N04_unit_properties_b10', set(ue) == set(I.UNIT_SHOW) and 'b9' not in flat
         and ue['zprobe-run-b10@check.service']['FragmentPath'] == '/etc/systemd/system/zprobe-run-b10@.service'
         and ue['zprobe-journal-b10@check.service']['FragmentPath']
         == '/etc/systemd/system/zprobe-journal-b10@.service'
         and ue['zprobe-run-b10@check.service']['ExecStopPostEx'][1][1]
         == '/usr/bin/systemctl start --no-block zprobe-journal-b10@check.service'
         and ue['zprobe-journal-b10@check.service']['ExecStartEx'][0][1]
         == '/usr/bin/python3 -I /usr/local/lib/zavod/probes-b10/zprobe_journal.py commit check', flat[:300])
    case('N05_journal_anchor_kept_from_b9', (I.KNOWN_SERIES, I.EXPECT_DIGEST, I.EXPECT_LAST)
         == (B9.KNOWN_SERIES, B9.EXPECT_DIGEST, B9.EXPECT_LAST) and len(I.EXPECT_DIGEST) == 64
         and 'СВЕРИТЬ ЧТЕНИЕМ НА СЕРВЕРЕ' in read(I.__file__).decode('utf-8'))


def t_targets():
    pkg = fake_pkg()
    tg = I.targets(pkg)
    paths = [p for p, _, _ in tg]
    lib, ud = I.LIB, I.UNIT_DIR
    want = {lib} | {os.path.join(lib, n) for n in I.LIB_FILES} | {os.path.join(lib, 'RELEASE'),
                                                                  os.path.join(lib, 'zprobe_pins_b9.txt'),
                                                                  os.path.join(lib, 'INSTALLED.sha256')}
    want |= {os.path.join(ud, u) for u in I.UNITS}
    modes = {p: m for p, _, m in tg}
    case('N06_targets_b10', tg[0] == (lib, None, 0o755) and paths[-1] == os.path.join(lib, 'INSTALLED.sha256')
         and set(paths) == want and len(paths) == len(want)
         and modes[os.path.join(lib, 'zprobe-start')] == 0o755 and modes[os.path.join(lib, 'zprobe_pins_b9.txt')] == 0o644
         and modes[paths[-1]] == 0o644
         and dict((p, d) for p, d, _ in tg)[os.path.join(lib, 'zprobe_pins_b9.txt')]
         == read(os.path.join(REPO, 'zavod', 'ops', 'zprobe_pins_b9.txt')), sorted(set(paths) ^ want))
    data = tg[-1][1]
    text = data.decode('ascii')
    lines = text.split('\n')
    files = {p: d for p, d, _ in tg[:-1] if d is not None}
    got = {}
    fmt_ok = text.endswith('\n') and lines[-1] == ''
    for ln in lines[:-1]:
        m = UN.INSTALLED_LINE.fullmatch(ln)
        if not m:
            fmt_ok = False
            break
        got[m.group(2)] = m.group(1)
    order = [ln.split('  ', 1)[1] for ln in lines[:-1]]
    case('N07_installed_list_format', fmt_ok and order == sorted(order) and len(order) == len(set(order))
         and got == {p: sha(d) for p, d in files.items()} and paths[-1] not in got
         and order.count('/etc/systemd/system/zprobe-run-b10@.service') == 1, text[:300])
    d = tmp()
    p = os.path.join(d, 'INSTALLED.sha256')
    put(p, data, 0o644)
    unit = files['/etc/systemd/system/zprobe-run-b10@.service']
    if not ROOT:                 # expected_fragment: O_NOFOLLOW и владелец root — только Linux root
        skip('N08_installed_list_accepted_by_expected_fragment')
    else:
        case('N08_installed_list_accepted_by_expected_fragment',
             UN.expected_fragment(p) == {'path': UN.TEMPLATE, 'sha': sha(unit)} and UN.TEMPLATE == I.template_path(),
             UN.expected_fragment(p))
    p2 = os.path.join(d, 'INSTALLED2.sha256')
    put(p2, data.replace(b'/etc/systemd/system/zprobe-run-b10@.service', b'/etc/systemd/system/zprobe-run-b9@.service'),
        0o644)
    if not ROOT:                 # expected_fragment: O_NOFOLLOW и владелец root — только Linux root
        skip('N09_list_without_b10_template_refused')
    else:
        case('N09_list_without_b10_template_refused', UN.expected_fragment(p2) is None)
    return pkg


def fake_b9(base, pkg_pins_dir):
    """Дерево B9 в папке испытания и отпечатки B9 к нему (ключи — как у настоящего zprobe_pins_b9.txt)."""
    lib, ud = os.path.join(base, 'probes-b9'), os.path.join(base, 'sd')
    os.makedirs(lib)
    os.makedirs(ud, exist_ok=True)
    pins = {k: 'e' * 64 for k in I.B9_PIN_KEYS}
    for k in I.B9_LIB_KEYS:
        b = f'b9 {k}\n'.encode()
        put(os.path.join(lib, k), b)
        pins[k] = sha(b)
    for u in I.B9_UNITS:
        b = f'[Unit]\nDescription={u}\n'.encode()
        put(os.path.join(ud, u), b)
        pins[u] = sha(b)
    commit = 'c' * 40
    put(os.path.join(lib, 'RELEASE'), f'commit={commit}\nversion=3.5.5-b9\n'.encode())
    body = '# pins B9\nrelease_commit ' + commit + '\n' + ''.join(f'{k} {v}\n' for k, v in pins.items())
    put(os.path.join(pkg_pins_dir, I.PINS_B9_SRC), body.encode())
    return lib, ud


def t_b9_check():
    base, pkg = tmp(), tmp()
    lib, ud = fake_b9(base, pkg)
    keep = (I.LIB, I.UNIT_DIR, I.B9_LIB)
    set_paths(I.LIB, ud, lib)
    try:
        real = set(B9.read_pins_file(os.path.join(REPO, I.PINS_B9_SRC), I.B9_PIN_KEYS))
        case('N10_b9_pin_keys_equal_real_b9_pins', real == set(I.B9_PIN_KEYS) | {'release_commit'})
        p0 = I.b9_problems(pkg)
        case('N11_b9_untouched_ok', p0 == [], p0)
        rp = os.path.join(lib, 'zprobe_runner.py')
        orig = read(rp)
        put(rp, orig + b'# changed\n')
        p1 = I.b9_problems(pkg)
        case('N12_b9_changed_file_flagged', p1 == [f'B9 {rp} differs from B9 pins'], p1)
        put(rp, orig)
        up = os.path.join(ud, 'zprobe-journal-b9@.service')
        uorig = read(up)
        put(up, uorig + b'ExecStart=/bin/false\n')
        p2 = I.b9_problems(pkg)
        case('N13_b9_changed_unit_flagged', p2 == [f'B9 {up} differs from B9 pins'], p2)
        put(up, uorig)
        put(os.path.join(lib, 'zprobe_seal.py'), b'x\n')
        p3 = I.b9_problems(pkg)
        case('N14_b9_extra_file_flagged', len(p3) == 1 and 'holds other files' in p3[0] and 'zprobe_seal.py' in p3[0],
             p3)
        lib2 = os.path.join(base, 'probes-b9-r')
        shutil.copytree(lib, lib2, ignore=shutil.ignore_patterns('zprobe_seal.py'))
        set_paths(I.LIB, ud, lib2)
        put(os.path.join(lib2, 'RELEASE'), b'commit=' + b'd' * 40 + b'\nversion=3.5.5-b9\n')
        p4 = I.b9_problems(pkg)
        case('N15_b9_release_changed_flagged', p4 == ['B9 RELEASE differs from the B9 release commit'], p4)
        rep, rest, old = REL.Report(), [], I._b9_common
        try:
            I._b9_common = lambda _pkg, _rep: rest.append('rest')     # остальной список B9 здесь не нужен
            I.common(pkg, rep)
        finally:
            I._b9_common = old
        case('N16_common_reports_b9_first', B9.common is I.common and rep.lines
             and rep.lines[0].startswith('CHECK B9 FAIL') and rest == ['rest'], rep.lines)
    finally:
        set_paths(*keep)


def t_sql_and_builder():
    import zprobe_release as Z
    case('N17_sql_name_override', Z.SQL_FILE == '06_zavod_ext_04.sql' and REL.SQL_FILE == '06_zavod_ext_04.sql'
         and B9B_SQL_BEFORE == 'zavod/kernel/db/06_zavod_ext_04.sql' and BB.SQL == 'zavod/kernel/db/08_zavod_ext_06.sql'
         and BB.SQL in BB.B.FILES and not any(f.endswith('06_zavod_ext_04.sql') for f in BB.B.FILES)
         and os.path.isfile(os.path.join(REPO, BB.SQL)), (Z.SQL_FILE, B9B_SQL_BEFORE, BB.SQL))
    B = BB.B
    P = B.PROBES
    files, keys = set(B.FILES), dict(B.PIN_KEYS)
    need = {P + n for n in NEW} | {P + 'zprobe_release_b9.py', P + 'zprobe_release_b10.py', P + 'zprobe_release.py',
                                   P + 'zprobe-run-b10@.service', P + 'zprobe-journal-b10@.service',
                                   'zavod/ops/zprobe_pins_b9.txt', 'zavod/ops/zprobe_pins_b8.txt'}
    missing = sorted(need - files) + sorted(f for f in B.FILES if not os.path.isfile(os.path.join(REPO, f)))
    case('N18_builder_files_have_every_new_module', not missing and not any('-b9@' in f for f in B.FILES)
         and len(B.FILES) == len(files), missing)
    want_keys = {'pb1_session.py', 'zprobe_rules.py', 'zprobe_runner.py', 'zprobe_journal.py', 'zprobe-start',
                 'zprobe-run-b10@.service', 'zprobe-journal-b10@.service', 'zagent@.service', 'zavod-proxy',
                 'zavod-gate', 'zavod-egress.nft', 'phone_zprobe_verify.py', 'phone_zprobe_rules.py',
                 'pc_zprobe_refs.sh', 'pc_zprobe_refs_check.py', 'pc_zprobe_rules.py', 'pc_zprobe_verify_export.py',
                 'pc_zprobe_export_rules.py', 'pc_zprobe_seal.py'} | set(NEW)
    case('N19_builder_pin_keys', set(keys) == want_keys and len(keys) == len(B.PIN_KEYS)
         and all(p in files for p in keys.values()), sorted(set(keys) ^ want_keys))
    case('N20_builder_names', B.VERSION == '3.5.5-b10' and B.PINS_PATH == 'zavod/ops/zprobe_pins_b10.txt'
         and B.SH_PATH == P + 'zprobe-release-3.5.5-b10.sh'
         and {P + 'zprobe-start', P + 'zprobe_release_b10.py'} <= B.EXEC
         and 'zprobe_release_b10.py" "$M"' in B.SH_TEMPLATE and 'ВЫПУСК: 3.5.5 B10' in B.SH_TEMPLATE
         and 'zprobe_release_b9.py' not in B.SH_TEMPLATE)
    # клетка: отпечатки дерева = отпечатки B9 и B8 (как проверяет build); чужая сумма — отказ
    tree = {k: sha(read(os.path.join(REPO, p))) for k, p in B.PIN_KEYS}
    p8 = B9B.parse(read(os.path.join(REPO, 'zavod', 'ops', 'zprobe_pins_b8.txt')))
    p9 = B9B.parse(read(os.path.join(REPO, 'zavod', 'ops', 'zprobe_pins_b9.txt')))
    case('N21_builder_cell_equals_b8_and_b9_pins', B9B.cell_problem(tree, p8) is None
         and B9B.cell_problem(tree, p9) is None
         and B9B.cell_problem(dict(tree, **{'zavod-gate': '0' * 64}), p9) is not None)


def t_code_names():
    def code(n):
        return '\n'.join(code_lines(read(os.path.join(PROBES, n)).decode('utf-8')))
    st, rn, jn = code('zprobe-start'), code('zprobe_runner.py'), code('zprobe_journal.py')
    case('N22_start_runner_journal_use_b10_names', 'probes-b9' not in st + rn + jn and '-b9@' not in st + rn + jn
         and 'LIB=/usr/local/lib/zavod/probes-b10' in st and "LIB = '/usr/local/lib/zavod/probes-b10'" in rn
         and "'/etc/systemd/system/zprobe-run-b10@.service', '/etc/systemd/system/zprobe-journal-b10@.service'" in rn
         and "unit = f'zprobe-journal-b10@{series}.service'" in jn)
    block = st.split('if [ "${1:-}" = "--seal-residue" ]; then\n', 1)[-1].split('\nfi\n', 1)[0]
    case('N23_start_seal_residue_and_rc', '  [ $# = 2 ] && [ "$2" = pb1trial2 ] || die ' in block
         and block.rstrip().endswith('exec /usr/bin/python3 -I "$LIB/zprobe_r2.py" pb1trial2')
         and st.index('--seal-residue') > st.index('[ "$(id -u)" = 0 ] || die')
         and '  exec /usr/bin/python3 -I "$LIB/zprobe_r2.py" pb1trial2\n' in st
         and 'URC=$?' in st and 'unit_rc=$URC' in st and 'exit "$URC"' in st and 'retry_rc=$RRC' in st
         and 'unit_rc=$?' not in st)
    ph = read(os.path.join(REPO, 'zavod', 'ops', 'phone', 'zprobe_series.sh')).decode('utf-8')
    case('N24_phone_starts_b10', '/usr/local/lib/zavod/probes-b10/zprobe-start "$S"' in ph
         and 'probes-b9/zprobe-start "$S"' not in ph)


def t_root_install(pkg):
    """Linux root: настоящий проход создания целей (план B9-порядка + REL.apply) в папке испытания."""
    names = ('N25_install_writes_installed_list_root_0644', 'N26_installed_list_check_ok',
             'N27_second_plan_creates_nothing', 'N28_changed_installed_file_flagged')
    if not ROOT:
        for n in names:
            skip(n)
        return
    base = tmp()
    os.chmod(base, 0o755)
    for d in ('lib', 'sd', 'j'):
        os.mkdir(os.path.join(base, d), 0o755 if d != 'j' else 0o700)
    keep = (I.LIB, I.UNIT_DIR, I.B9_LIB, REL.JOURNAL_DIR)
    set_paths(os.path.join(base, 'lib', 'probes-b10'), os.path.join(base, 'sd'))
    REL.JOURNAL_DIR = os.path.join(base, 'j')
    try:
        tg = I.targets(pkg)
        acts, probs = B9.plan(pkg)
        done = []
        j = REL.Journal('20261115T000000Z')
        try:
            REL.apply(acts, done, j)
            I.sync_dirs(tg)
        finally:
            j.close()
        p = I.installed_path()
        st = os.lstat(p)
        case(names[0], not probs and len(done) == len(tg) and stat.S_ISREG(st.st_mode) and st.st_nlink == 1
             and (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) == (0, 0, 0o644) and read(p) == tg[-1][1]
             and UN.expected_fragment(p, I.template_path())
             == {'path': I.template_path(), 'sha': sha(read(I.template_path()))}, (probs, done[-2:], oct(st.st_mode)))
        pr = I.installed_problems(pkg)
        case(names[1], pr == [], pr)
        acts2, probs2 = B9.plan(pkg)
        case(names[2], acts2 == [] and probs2 == [], (acts2[:2], probs2[:2]))
        tp = os.path.join(I.LIB, 'zprobe_r2.py')
        with open(tp, 'ab') as f:            # подмена файла испытания в своей папке
            f.write(b'# changed\n')
        pr2 = I.installed_problems(pkg)
        case(names[3], f'{tp} differs from INSTALLED.sha256' in pr2, pr2)
    finally:
        set_paths(*keep[:3])
        REL.JOURNAL_DIR = keep[3]


def main():
    t_names()
    pkg = t_targets()
    t_b9_check()
    t_sql_and_builder()
    t_code_names()
    t_root_install(pkg)
    res = 'FAIL' if not OK else ('PASS_NO_ROOT' if SKIPPED else 'PASS')
    print(f'ZPROBE_RELEASE_B10_TEST={res}')
    return 0 if OK else 1


if __name__ == '__main__':
    sys.exit(main())
