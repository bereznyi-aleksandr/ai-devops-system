#!/usr/bin/python3
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_release_b10.py
# ВЕРСИЯ: v0.3 (выпуск B10)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-15 00:18 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-15 19:42 +02:00
# v0.3 (REL74 REVISE 0/1/2): байт-код B9 допускается, только если доказанно равен исходнику (заголовок, время,
#   размер, объект кода = compile() закреплённого .py; M-01); службы B10 с -B; полный якорь в N05 (L-01); N29–N31 (L-02).
# v0.2 (Claude, терминал zavod; preflight на zavod-1 2026-11-15 16:58Z дал FAIL 3, REL73): якорь журнала и отметки
#   начала — после pb1trial2 (по чтению на сервере); допуск папки __pycache__ в probes-b9 (байт-код модулей B9,
#   root, без записи группе и прочим; иной файл — FAIL). Испытания N05 (новый якорь), N17–N19.
# ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · напарник · 04» (869221b9), помощник
# НАЗНАЧЕНИЕ: установка B10 рядом с B8 и B9 (проект DESIGN_B10_3_5_5_20261114_v0_18.md раздел 7; 1.3 Б; 1.6).
#   Построена на zprobe_release_b9.py: тот же модуль берётся целиком, меняются только его переменные и несколько
#   функций (так же build_release_3_5_5_b9.py берёт build_release_3_5_5.py). Отличия от B9:
#   - папка программ /usr/local/lib/zavod/probes-b10, службы zprobe-run-b10@ и zprobe-journal-b10@;
#   - в папке программ ещё модули B10 (zprobe_dropin, zprobe_checks, zprobe_seal, zprobe_unstarted,
#     zprobe_export_rules, zprobe_export, zprobe_r2, zevidence_send) и копия отпечатков B9 zprobe_pins_b9.txt (по ней
#     zprobe_r2.py находит эталон службы B9, ключ zprobe-run-b9@.service);
#   - последней целью пишется список установленных файлов LIB/INSTALLED.sha256: новый файл (O_EXCL, тем же
#     порядком дневника INTENT → CREATED → DONE, что остальные цели), root, 0644, fsync файла, затем fsync папок;
#     строка «<64 знака sha256>  <полный путь>» на каждый установленный файл, по пути, в конце перевод строки
#     (формат zprobe_unstarted.INSTALLED_LINE; шаблон /etc/systemd/system/zprobe-run-b10@.service — ровно один раз);
#   - B9 цел: каждый файл B9 (папка probes-b9 и службы *-b9@) равен отпечаткам B9 (zavod/ops/zprobe_pins_b9.txt в
#     пакете), RELEASE B9 — коммиту выпуска B9, в папке B9 нет лишних файлов; проверка B8 остаётся как в B9.
#   Режимы те же: preflight | verify-installed | install <пакет> | report <пакет> preflight|verify-installed.
#   verify-installed ещё сверяет INSTALLED.sha256 с ожидаемым списком (байт в байт, эталон шаблона, суммы файлов).
# ОГРАНИЧЕНИЯ: B8 и B9 только читаются; ничего не удаляется, не переименовывается и не перезаписывается. Модуль
#   меняет переменные zprobe_release_b9 и zprobe_release в своём процессе — не импортировать вместе с установкой B9
#   в одном процессе. SQL 08_zavod_ext_06.sql этот файл не ставит (отдельный шаг раздела 7).
import datetime
import importlib.util
import marshal
import os
import re
import stat
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zprobe_release_b9 as B9  # noqa: E402
import zprobe_unstarted as UN  # noqa: E402

REL = B9.REL

# пути — переменные модуля (испытания подменяют их на папку испытания)
LIB = '/usr/local/lib/zavod/probes-b10'
B9_LIB = '/usr/local/lib/zavod/probes-b9'
UNIT_DIR = B9.UNIT_DIR
UNITS = ('zprobe-run-b10@.service', 'zprobe-journal-b10@.service')
B9_UNITS = ('zprobe-run-b9@.service', 'zprobe-journal-b9@.service')
NEW_MODULES = ('zprobe_dropin.py', 'zprobe_checks.py', 'zprobe_seal.py', 'zprobe_unstarted.py',
               'zprobe_export_rules.py', 'zprobe_export.py', 'zprobe_r2.py', 'zevidence_send.py')
LIB_FILES = dict(B9.LIB_FILES, **{n: 0o644 for n in NEW_MODULES})   # zprobe-start остаётся 0755
B9_LIB_KEYS = tuple(B9.LIB_FILES)                                    # программы B9 в папке probes-b9
PINS_B9_SRC = os.path.join('zavod', 'ops', 'zprobe_pins_b9.txt')     # в пакете
PINS_B9_NAME = 'zprobe_pins_b9.txt'                                  # копия в LIB (читает zprobe_r2.py)
INSTALLED_NAME = 'INSTALLED.sha256'
B9_RELEASE_VERSION = '3.5.5-b9'
UNIT_SHOW = ('zprobe-journal-b10@check.service', 'zprobe-run-b10@check.service')
WATCH_UNITS = ('zprobe-run@*', 'zprobe-run-b9@*', 'zprobe-journal-b9@*', 'zprobe-run-b10@*', 'zprobe-journal-b10@*',
               'zagent@*')
# Ключи отпечатков B9 (zavod/ops/zprobe_pins_b9.txt) — строгий разбор: ровно эти и release_commit.
B9_PIN_KEYS = B9_LIB_KEYS + B9_UNITS + tuple(B9.B8_CELL) + (
    'phone_zprobe_verify.py', 'phone_zprobe_rules.py', 'pc_zprobe_refs.sh', 'pc_zprobe_refs_check.py',
    'pc_zprobe_rules.py')

# Якорь журнала и отметки начала — состояние ПОСЛЕ pb1trial2, внесено по чтению на сервере (как в B9 v0.5): запуск
# STAGE_AND_PREFLIGHT на zavod-1 2026-11-15 16:58Z (снимок STAGE_PREFLIGHT_B10_SCREEN_20261115_1859.jpg, строка
# CHECK JOURNAL: segments=2 seq=4 digest b8a27a36… last_sha256 ce3a9b0f…; CHECK STARTED: ['pb1trial1', 'pb1trial2']).
# Сегмент 000001.jsonl — серия pb1trial1, 000002.jsonl — pb1trial2 (по порядку STARTED_SERIES).
STARTED_SERIES = ('pb1trial1', 'pb1trial2')
KNOWN_SERIES = ','.join(STARTED_SERIES)      # для строки отчёта CHECK STARTED
EXPECT_SEGMENTS, EXPECT_SEQ = 2, 4
EXPECT_DIGEST = 'b8a27a36fb2076ee004baf286df941baa0b417dfbe9537802b435e5a64bcdb8d'  # R.segments_digest после pb1trial2
EXPECT_LAST = 'ce3a9b0fdc5c1b08e597213461980aea9d4e4e791955510f2fee2d0f5d01e114'    # SHA-256 последней строки после pb1trial2
# __pycache__ в папке B9: службы B9 запускают python3 -I без -B от root (zprobe-run-b9@, ExecStart=+), и Python
# пишет байт-код модулей B9 рядом с ними. Допускается только эта папка: настоящая, root, без записи группе и прочим,
# внутри только файлы <модуль B9>.<cache_tag этого python3>.pyc (root, одна ссылка, без записи группе и прочим), и
# каждый ДОКАЗАННО равен исходнику B9 (M-355-REL74-01): заголовок — MAGIC этого python3, флаги 0 (проверка по времени
# и размеру исходника), время и размер = у закреплённого .py; объект кода (marshal.loads, код не исполняется) равен
# compile() этого .py (уровень оптимизации 0, как у служб B9 без -O). Иначе FAIL. Службы B10 запускаются с -B.
B9_PYCACHE = '__pycache__'
PYC_NAME = re.compile(r'([A-Za-z0-9_]+)\.([a-z]+-[0-9]+)\.pyc')

_b9_targets = B9.targets
_b9_common = B9.common
_b9_unit_expect = B9.unit_expect
_b9_verify_installed = B9.verify_installed
_b9_journal_problems = B9.journal_problems


def installed_path():
    return os.path.join(LIB, INSTALLED_NAME)


def template_path():
    """1.3 Б: эталон файла службы B10 — этот путь и его сумма в INSTALLED.sha256."""
    return os.path.join(UNIT_DIR, UNITS[0])


def installed_bytes(tg):
    """Список установленных файлов: строка «<sha256>  <путь>» на каждый файл целей (папки — без строки), по пути."""
    lines = sorted((path, REL.sha_b(data)) for path, data, _ in tg if data is not None)
    return ''.join(f'{h}  {p}\n' for p, h in lines).encode('ascii')


def targets(pkg):
    """Цели B10: цели B9-порядка (папка LIB, программы, RELEASE, службы) с переменными B10, затем копия отпечатков B9
    и последней — INSTALLED.sha256 со списком всех предыдущих файлов."""
    out = _b9_targets(pkg)
    with open(os.path.join(pkg, PINS_B9_SRC), 'rb') as f:
        out.append((os.path.join(LIB, PINS_B9_NAME), f.read(), 0o644))
    out.append((installed_path(), installed_bytes(out), 0o644))
    return out


def unit_expect():
    """Свойства служб B10: те же, что у B9, имена служб — b10 (папка программ уже LIB B10), python3 -I -B."""
    def fix(v):
        if isinstance(v, str):
            return (v.replace('zprobe-journal-b9@', 'zprobe-journal-b10@').replace('zprobe-run-b9@', 'zprobe-run-b10@')
                    .replace(f'/usr/bin/python3 -I {LIB}/', f'/usr/bin/python3 -I -B {LIB}/'))
        if isinstance(v, list):
            return [tuple(fix(x) for x in t) for t in v]
        return v
    return {u: {k: fix(v) for k, v in want.items()} for u, want in _b9_unit_expect().items()}


def b9_problems(pkg):
    """B9 цел (только чтение): файлы B9 — те же SHA-256, что в отпечатках B9; RELEASE B9 — коммит выпуска B9; в папке
    B9 ровно её программы и RELEASE."""
    pins = B9.read_pins_file(os.path.join(pkg, PINS_B9_SRC), B9_PIN_KEYS)
    files = {k: os.path.join(B9_LIB, k) for k in B9_LIB_KEYS}
    files.update({u: os.path.join(UNIT_DIR, u) for u in B9_UNITS})
    probs = []
    for k, p in sorted(files.items()):
        try:
            st = os.lstat(p)
        except OSError as x:
            probs.append(f'B9 {p} {type(x).__name__}')
            continue
        if not stat.S_ISREG(st.st_mode):
            probs.append(f'B9 {p} is not a plain file')
        elif REL.sha(p) != pins[k]:
            probs.append(f'B9 {p} differs from B9 pins')
    try:
        if os.path.islink(B9_LIB) or not os.path.isdir(B9_LIB):
            probs.append(f'B9 {B9_LIB} is not a plain folder')
        else:
            extra = sorted(set(os.listdir(B9_LIB)) - set(B9_LIB_KEYS) - {'RELEASE', B9_PYCACHE})
            if extra:
                probs.append(f'B9 {B9_LIB} holds other files: {extra[:5]}')
            probs += pycache_problems()[0]
    except OSError as x:
        probs.append(f'B9 {B9_LIB} {type(x).__name__}')
    try:
        with open(os.path.join(B9_LIB, 'RELEASE'), 'rb') as f:
            rel = f.read()
        if rel != f'commit={pins["release_commit"]}\nversion={B9_RELEASE_VERSION}\n'.encode():
            probs.append('B9 RELEASE differs from the B9 release commit')
    except OSError as x:
        probs.append(f'B9 RELEASE {type(x).__name__}')
    return probs


ROOT_UID = 0   # владелец папки байт-кода и её файлов (испытания без root подменяют на свой uid)


def pycache_problems():
    """Папка байт-кода B9 (только чтение): ([замечания], [имена .pyc]). Её нет — ([], [])."""
    d = os.path.join(B9_LIB, B9_PYCACHE)
    if not os.path.lexists(d):
        return [], []
    st = os.lstat(d)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != ROOT_UID or st.st_mode & 0o022:
        return [f'B9 {d} is not a plain root folder without group/other write'], []
    mods = {k[:-3] for k in B9_LIB_KEYS if k.endswith('.py')}
    probs, names = [], sorted(os.listdir(d))
    for n in names:
        m = PYC_NAME.fullmatch(n)
        fst = os.lstat(os.path.join(d, n))
        if not m or m.group(1) not in mods:
            probs.append(f'B9 {d} holds a file that is not bytecode of a B9 module: {n[:60]}')
        elif m.group(2) != sys.implementation.cache_tag:
            probs.append(f'B9 {d}/{n[:60]} is bytecode of another Python ({sys.implementation.cache_tag} here), '
                         'cannot be checked')
        elif not stat.S_ISREG(fst.st_mode) or fst.st_nlink != 1 or fst.st_uid != ROOT_UID or fst.st_mode & 0o022:
            probs.append(f'B9 {d}/{n[:60]} is not a plain single-link root file without group/other write')
        else:
            why = pyc_differs(os.path.join(d, n), os.path.join(B9_LIB, m.group(1) + '.py'))
            if why:
                probs.append(f'B9 {d}/{n[:60]} {why}')
    return probs, names


def pyc_differs(pyc, src):
    """'' — байт-код pyc доказанно равен исходнику src для этого python3; иначе причина. Только чтение; код из pyc не
    исполняется (marshal.loads строит объект кода, не запуская его)."""
    with open(pyc, 'rb') as f:
        data = f.read()
    with open(src, 'rb') as f:
        source = f.read()
    sst = os.stat(src)
    if len(data) < 16 or data[:4] != importlib.util.MAGIC_NUMBER:
        return 'header is not this Python bytecode header'
    if int.from_bytes(data[4:8], 'little') != 0:
        return 'is hash-based bytecode (flags != 0), not the timestamp form the services write'
    if (int.from_bytes(data[8:12], 'little'), int.from_bytes(data[12:16], 'little')) \
            != (int(sst.st_mtime) & 0xFFFFFFFF, sst.st_size & 0xFFFFFFFF):
        return 'header time/size differ from the pinned source'
    try:
        got = marshal.loads(data[16:])
    except (EOFError, ValueError, TypeError) as x:
        return f'bytecode does not load: {type(x).__name__}'
    want = compile(source, src, 'exec', dont_inherit=True, optimize=0)
    if not isinstance(got, types.CodeType) or got != want:
        return 'bytecode differs from compile() of the pinned source'
    return ''


def started_problems(zp):
    """Отметки начала после pb1trial2: started — настоящая папка zprobe 0750; ровно STARTED_SERIES; сегмент i журнала
    начинается SERIES_START серии STARTED_SERIES[i], отметка серии — обычный файл с одной ссылкой, байты = marker с
    challenge этого SERIES_START. Только чтение."""
    sd = os.path.join(B9.DATA, 'started')
    s = REL.state_dir(sd, 0o750, zp.pw_uid, zp.pw_gid)
    if s != 'same':
        return [f'started: {s}']
    names = sorted(os.listdir(sd))
    if names != sorted(STARTED_SERIES):
        return [f'started must hold exactly {list(STARTED_SERIES)}, has {names[:5]}']
    segs = B9.J.read_segments(os.path.join(B9.DATA, 'journal'))
    if len(segs) != len(STARTED_SERIES):
        return [f'journal must hold {len(STARTED_SERIES)} segments, has {len(segs)}']
    probs = []
    for (seg, data), series in zip(segs, STARTED_SERIES):
        first = B9.J.json.loads(data.split(b'\n')[0])
        p = os.path.join(sd, series)
        st = os.lstat(p)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            probs.append(f'started mark {series} is not a plain single-link file')
            continue
        with open(p, 'rb') as f:
            got = f.read()
        if first.get('kind') != 'SERIES_START' or first.get('series') != series \
                or got != B9.J.marker(series, first.get('challenge')):
            probs.append(f'started mark {series} differs from the SERIES_START of {seg}')
    return probs


def journal_problems():
    """Шлюз журнала B9 (только чтение) с якорем после pb1trial2; текст замечания — про pb1trial2."""
    probs, line = _b9_journal_problems()
    return [p.replace('after pb1trial1', 'after pb1trial2') for p in probs], line


def common(pkg, rep):
    """Проверка B9 (новая в B10), затем общий список B9 (B8, службы, учётная запись, журнал, отметки)."""
    p = b9_problems(pkg)
    pyc = [] if p else pycache_problems()[1]
    rep.add('B9', 'FAIL' if p else 'OK', '; '.join(p) or (
        f'- (B9 bytecode folder {B9_PYCACHE}: {len(pyc)} .pyc of B9 modules, tolerated)' if pyc else '-'))
    return _b9_common(pkg, rep)


def installed_problems(pkg):
    """INSTALLED.sha256 = ожидаемый список (root, 0644, байт в байт); эталон шаблона по zprobe_unstarted
    .expected_fragment — путь шаблона B10 и сумма файла службы выпуска; каждый файл списка сейчас с той же суммой."""
    tg = targets(pkg)
    path, data, mode = tg[-1]
    s = B9.target_state(path, data, mode)
    if s != 'same':
        return [f'{path}: {s}']
    probs = []
    unit = {p: d for p, d, _ in tg}.get(template_path())
    frag = UN.expected_fragment(path, template_path())
    if unit is None or frag != {'path': template_path(), 'sha': REL.sha_b(unit)}:
        probs.append(f'{path}: template line of {template_path()} is missing, repeated or differs')
    for ln in data.decode('ascii').split('\n')[:-1]:
        h, _, p = ln.partition('  ')
        try:
            got = REL.sha(p)
        except OSError as x:
            probs.append(f'{p} {type(x).__name__}')
            continue
        if got != h:
            probs.append(f'{p} differs from {INSTALLED_NAME}')
    return probs


def verify_installed(pkg, rep):
    _b9_verify_installed(pkg, rep)
    p = installed_problems(pkg)
    rep.add('INSTALLED_LIST', 'FAIL' if p else 'OK', '; '.join(p) or installed_path())


def sync_dirs(tg):
    """Папки целей и родитель LIB — fsync после создания файлов (запись имён в папках на диске)."""
    for d in sorted({os.path.dirname(path) for path, _, _ in tg} | {os.path.dirname(LIB)}):
        fd = os.open(d, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def install(pkg, rep):
    """Как install B9 (проверки, план, дневник, daemon-reload, systemd-analyze verify, verify-installed), итоги
    ZPROBE_B10_INSTALL; после создания целей — fsync папок."""
    lock = REL.install_lock()
    if lock is None:
        print('ZPROBE_B10_INSTALL=REFUSED another install is running; nothing changed')
        return 1
    try:
        zp = common(pkg, rep)
        tg = targets(pkg)
        p = B9.parent_problems(tg)
        rep.add('PARENTS', 'FAIL' if p else 'OK', '; '.join(sorted(set(p))) or '-')
        if rep.fails or zp is None:
            print(f'ZPROBE_B10_INSTALL=REFUSED checks fails={rep.fails}; nothing created')
            return 1
        acts, probs = B9.plan(pkg)
        if probs or not acts:
            for x in probs:
                print('CONFLICT ' + x)
            print('ZPROBE_B10_INSTALL=REFUSED ' + ('conflicts=%d' % len(probs) if probs else 'already installed')
                  + '; nothing created')
            return 1
        done = []
        os.umask(0o077)
        j = REL.Journal(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        try:
            REL.apply(acts, done, j)
            sync_dirs(tg)
        except Exception as x:  # noqa: BLE001
            print(f'ZPROBE_B10_INSTALL=PARTIAL created={done} journal={j.path} error={type(x).__name__}: {x}; '
                  'nothing removed; run install again: it finishes only objects of this release from the journal')
            return 1
        finally:
            j.close()
        rc0, _, e0 = B9.sh('systemctl', 'daemon-reload')
        rc1, o1, e1 = B9.sh('systemd-analyze', 'verify', *UNIT_SHOW)
        print(f'INSTALLED_NEW={done} journal={j.path} daemon_reload_rc={rc0} verify_rc={rc1} '
              f'{(e0 + o1 + e1).strip()[:200]}')
        rep2 = REL.Report()
        verify_installed(pkg, rep2)
        ok = rc0 == 0 and rc1 == 0 and not rep2.fails
        print('ZPROBE_B10_INSTALL=' + ('OK' if ok else 'REFUSED installed state does not match; nothing removed'))
        return 0 if ok else 1
    finally:
        os.close(lock)


# Переменные и функции модуля B9 — на значения B10 (функции B9 берут их из своего модуля в момент вызова).
B9.LIB, B9.UNITS, B9.LIB_FILES, B9.UNIT_SHOW, B9.WATCH_UNITS = LIB, UNITS, LIB_FILES, UNIT_SHOW, WATCH_UNITS
B9.KNOWN_SERIES, B9.EXPECT_SEGMENTS, B9.EXPECT_SEQ = KNOWN_SERIES, EXPECT_SEGMENTS, EXPECT_SEQ
B9.EXPECT_DIGEST, B9.EXPECT_LAST = EXPECT_DIGEST, EXPECT_LAST
B9.targets, B9.common, B9.unit_expect, B9.verify_installed = targets, common, unit_expect, verify_installed
B9.started_problems, B9.journal_problems = started_problems, journal_problems
REL.LIB = LIB
REL.JOURNAL_PREFIX = 'zprobe-install-3.5.5-b10-'
REL.TESTS = '/var/lib/zavod/probes-tests-b10'
# REL.SQL_FILE не меняется: CHECK 09 (тело lease_reserve_start из 06_zavod_ext_04.sql) относится к режиму check B8,
# установка B10 его не вызывает; файл SQL B10 (08_zavod_ext_06.sql) кладёт в пакет сборщик B10.


def sync_paths():
    """Испытания меняют LIB, UNIT_DIR, B9_LIB этого модуля — те же значения нужны модулям B9 и выпуска."""
    B9.LIB, B9.UNIT_DIR, REL.LIB = LIB, UNIT_DIR, LIB


def main():
    a = sys.argv[1:]
    modes = {'preflight': B9.preflight, 'verify-installed': verify_installed}
    ok = os.geteuid() == 0 and ((len(a) == 2 and a[0] in ('preflight', 'verify-installed', 'install')) or
                                (len(a) == 3 and a[0] == 'report' and a[2] in modes))
    if not ok:
        print('usage (root): zprobe_release_b10.py preflight|verify-installed|install <package dir> | '
              'report <package dir> preflight|verify-installed')
        return 2
    pkg = os.path.abspath(a[1])
    rep = REL.Report()
    try:
        if a[0] == 'install':
            return install(pkg, rep)
        modes[a[2] if a[0] == 'report' else a[0]](pkg, rep)
    except Exception as x:  # noqa: BLE001 — всегда явный итог
        print(f'ZPROBE_B10_{a[0].upper()}=FAIL error={type(x).__name__}: {x}')
        return 1
    name = (a[2] if a[0] == 'report' else a[0]).upper().replace('-', '_')
    if a[0] == 'report':
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        path = REL.new_file(os.path.join(REL.JOURNAL_DIR, REL.JOURNAL_PREFIX + '{}.report'), stamp,
                            ('\n'.join(rep.lines) + '\n').encode('utf-8'))
        print(f'REPORT={path} SHA256={REL.sha(path)} (diagnostics, not a permission)')
    print(f'ZPROBE_B10_{name}={"FAIL" if rep.fails else "OK"} fails={rep.fails}')
    return 1 if rep.fails else 0


if __name__ == '__main__':
    sys.exit(main())
