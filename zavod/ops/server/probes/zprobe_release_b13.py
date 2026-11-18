#!/usr/bin/python3
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_release_b13.py
# ВЕРСИЯ: v0.2 (выпуск B13)  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-11-18 13:52 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-18 14:24 +02:00
# v0.2: только ACCEPTED-сумма zprobe_runner.py (бегунок v0.16: PINNED = все ключи кода отпечатков B13); логика та же.
# ИСПОЛНИТЕЛЬ: Claude, терминал zavod (пускатель); автор, принять не может. Аудитор — ChatGPT.
# НАЗНАЧЕНИЕ: установка B13 рядом с B8, B9, B10, B11 и B12 по проекту DESIGN_B13_RELEASE_v0_3.md (разделы 2, 3; REL126 AGREED).
#   Строится на zprobe_release_b12.py: его модуль (и через него B11, B10, B9) берётся целиком, здесь свои цели и своя
#   проверка «B12 цел». Отличия от B12:
#   - папка программ /usr/local/lib/zavod/probes-b13 — ровно 14 файлов: 12 программ (набор B10 без zprobe_r2.py), RELEASE
#     и INSTALLED.sha256; копии отпечатков B9 в папке B13 нет (zprobe_r2.py в B13 не ставится);
#   - ДВЕ НОВЫЕ СЛУЖБЫ /etc/systemd/system/zprobe-run-b13@.service и zprobe-journal-b13@.service, затем daemon-reload и
#     systemd-analyze verify (как B10);
#   - INSTALLED.sha256 — строки «<sha256>  <путь>» на 12 программ, RELEASE и обе службы (формат B10): строка службы
#     zprobe-run-b13@.service нужна бегунку (zprobe_unstarted.expected_fragment — эталон файла службы), поэтому в списке
#     не 13, а 15 строк; в папке файлов ровно 14 (отличие от текста проекта п. 2.1 — на аудит);
#   - B8, B9, B10, B11 и B12 целы (только чтение): B8–B11 — проверками B12/B11/B10; B12 — как B12 сверял B11 (п. 3 б):
#     папка probes-b12 — обычная папка root:root 0755, ровно 10 файлов (7 модулей, RELEASE, zprobe_pins_b9.txt,
#     INSTALLED.sha256), каждый — обычный файл root:root 0644 с одной ссылкой; модули и копия отпечатков B9 — суммы из
#     zprobe_pins_b12.txt пакета; RELEASE — байт в байт «commit=<коммит B12>\nversion=3.5.5-b12\n»; INSTALLED.sha256 —
#     байт в байт список, собранный заново из отпечатков B12; посторонних файлов (в том числе __pycache__) нет;
#   - файлы отпечатков B8, B9, B10, B11 и B12 в пакете обязаны иметь известные SHA-256 (B8–B11 — как
#     zprobe_release_b12.PINS_FILE_SHA, B12 — 5d5b5bb0…), release_commit B12 — 20ae4a83…;
#   - модули «без изменений» (pb1_session, zprobe_rules, zprobe_seal, zprobe_export) равны отпечаткам B10 (rules и seal —
#     и B12), изменённые программы и обе службы — закреплённым ACCEPTED-суммам (иначе FAIL PKG_MODULES);
#   - дневник тот же (INTENT → CREATED → DONE, O_EXCL, fsync), префикс zprobe-install-3.5.5-b13-, папка испытаний
#     /var/lib/zavod/probes-tests-b13.
#   Режимы те же: preflight | verify-installed | install <пакет> | report <пакет> preflight|verify-installed.
#   install пишет только папку probes-b13 и две службы; любой сбой — итог PARTIAL с перечнем созданного (STOP), без
#   удаления (P4.702): повтор достраивает только объекты этого выпуска по дневнику.
# ОГРАНИЧЕНИЯ: B8–B12 только читаются; ничего не удаляется, не переименовывается и не перезаписывается. Модуль меняет
#   переменные zprobe_release_b9 (targets и др.) и zprobe_release в своём процессе — не импортировать вместе с установкой
#   B9–B12 в одном процессе. SQL этот выпуск не ставит. Службы и их запуск — только после аудита выпуска и «да» оператора.
import datetime
import os
import stat
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zprobe_release_b12 as B12  # noqa: E402

B11 = B12.B11
B10 = B12.B10
B9 = B12.B9
REL = B12.REL
UN = B10.UN

# пути — переменные модуля (испытания подменяют их на папку испытания; пути B8–B12 — в их модулях)
LIB = '/usr/local/lib/zavod/probes-b13'
UNIT_DIR = B9.UNIT_DIR
UNITS = ('zprobe-run-b13@.service', 'zprobe-journal-b13@.service')
PROGRAMS = ('pb1_session.py', 'zprobe_rules.py', 'zprobe_runner.py', 'zprobe_journal.py', 'zprobe-start',
            'zprobe_dropin.py', 'zprobe_checks.py', 'zprobe_seal.py', 'zprobe_unstarted.py', 'zprobe_export_rules.py',
            'zprobe_export.py', 'zevidence_send.py')
UNCHANGED = ('pb1_session.py', 'zprobe_rules.py', 'zprobe_seal.py', 'zprobe_export.py')
LIB_FILES = {n: (0o755 if n == 'zprobe-start' else 0o644) for n in PROGRAMS}
INSTALLED_NAME = B12.INSTALLED_NAME
PINS_B9_NAME = B12.PINS_B9_NAME
PINS_B8_SRC, PINS_B9_SRC, PINS_B10_SRC, PINS_B11_SRC = B12.PINS_B8_SRC, B12.PINS_B9_SRC, B12.PINS_B10_SRC, B12.PINS_B11_SRC
PINS_B12_SRC = os.path.join('zavod', 'ops', 'zprobe_pins_b12.txt')
B12_RELEASE_VERSION = '3.5.5-b12'
B12_RELEASE_COMMIT = '20ae4a839adcb6e98babd06f3fa344bce1f17f83'
# Известные суммы файлов отпечатков B8–B11 (как у B12) и B12 (файл замороженного выпуска B12 1d4d2caf6).
PINS_FILE_SHA = dict(B12.PINS_FILE_SHA)
PINS_FILE_SHA[PINS_B12_SRC] = '5d5b5bb09a9afb008646fa905f4e121e72ef3e6a37b66a8f2b0efe495884596d'
# Закреплённые ACCEPTED-суммы (проект п. 2.5; те же, что build_release_3_5_5_b13.ACCEPTED, для двух служб — свои):
# изменённые программы и службы B13. Другие байты — FAIL PKG_MODULES, новый код без нового аудита не пройдёт.
ACCEPTED_SHA = {'zprobe_dropin.py': '54d1e899fafaaea62e4dc572114c6730861a70fc7299ceaea201da9674c0258b',
                'zprobe_runner.py': '92050756d4f0d20ae327b55a71b0c6eb773212975e35d8a2965deeff18be6e6c',
                'zprobe_export_rules.py': 'e0fd54ffe5b0ecbe527472908e6538f0a690e15277d8adf51280e4faf5483af2',
                'zprobe_checks.py': 'cdbdaa573d37c8b5a8f8174de2765064bbc4fa896c17c885d51f7b4851d3f24d',
                'zprobe_journal.py': '61561714145bbefde230b723ae79e9bf68d0270908e13cd40cfc2acb0757d770',
                'zprobe-start': 'ddd7eece0d31bba60c28762b4d6c8ad18c3fc51dfdda404431e9e08e55d68dca',
                'zprobe_unstarted.py': 'a6e3a2ec71c69bad0d9703386b97087ac114b783cce4c7ad10489cd102f319ba',
                'zevidence_send.py': '3973c08bb1cbfd49677e0a33adefc92169380de698f2ca4aee8547f30a623216'}
UNIT_ACCEPTED_SHA = {'zprobe-run-b13@.service': 'a246ab2293eb5f4e6478c13cfa64e2682d346356bfe6d2d845fd972493b7dde0',
                     'zprobe-journal-b13@.service': 'f17a5217c87e87ec8bcbdde8b5e1575a7c89e9d4df514b11f4a3b95444d0a28d'}
# Ключи отпечатков B12 (zavod/ops/zprobe_pins_b12.txt) — строгий разбор: ровно эти и release_commit.
B12_PIN_KEYS = tuple(B12.LIB_FILES) + (PINS_B9_NAME,)
UNIT_SHOW = ('zprobe-journal-b13@check.service', 'zprobe-run-b13@check.service')
WATCH_UNITS = tuple(B10.WATCH_UNITS) + ('zprobe-run-b13@*', 'zprobe-journal-b13@*')


def installed_path():
    return os.path.join(LIB, INSTALLED_NAME)


def template_path():
    """Эталон файла службы B13 — этот путь и его сумма в INSTALLED.sha256 (zprobe_unstarted.expected_fragment)."""
    return os.path.join(UNIT_DIR, UNITS[0])


def read(path):
    with open(path, 'rb') as f:
        return f.read()


def pins12(pkg):
    """Отпечатки B12 из пакета: строгий разбор и коммит выпуска B12 (иначе REL.Refused)."""
    pins = B9.read_pins_file(os.path.join(pkg, PINS_B12_SRC), B12_PIN_KEYS)
    if pins['release_commit'] != B12_RELEASE_COMMIT:
        raise REL.Refused(f'zprobe_pins_b12.txt: release_commit {pins["release_commit"]} is not B12 {B12_RELEASE_COMMIT}')
    return pins


def targets(pkg):
    """Цели B13: (путь, байты, права); первой — папка LIB; затем 12 программ, RELEASE, две службы и последней —
    INSTALLED.sha256 со списком всех предыдущих файлов (формат B10: «<sha256>  <путь>», по пути)."""
    src = os.path.join(pkg, 'zavod', 'ops', 'server', 'probes')
    out = [(LIB, None, 0o755)]
    for n, mode in LIB_FILES.items():
        out.append((os.path.join(LIB, n), read(os.path.join(src, n)), mode))
    out.append((os.path.join(LIB, 'RELEASE'), read(os.path.join(pkg, 'RELEASE')), 0o644))
    for u in UNITS:
        out.append((os.path.join(UNIT_DIR, u), read(os.path.join(src, u)), 0o644))
    out.append((installed_path(), B10.installed_bytes(out), 0o644))
    return out


def pkg_problems(pkg):
    """Состав пакета: пять файлов отпечатков — известные суммы; отпечатки B12 — коммит B12; модули «без изменений» равны
    отпечаткам B10 (rules и seal — и B12); изменённые программы и обе службы — ACCEPTED-суммам."""
    probs = []
    for rel, want in sorted(PINS_FILE_SHA.items()):
        try:
            got = REL.sha_b(read(os.path.join(pkg, rel)))
        except OSError as x:
            probs.append(f'package {rel} {type(x).__name__}')
            continue
        if got != want:
            probs.append(f'package {rel} differs from the known B8-B12 release sum')
    if probs:
        return probs
    try:
        p10 = B11.pins10(pkg)
        p12 = pins12(pkg)
    except (OSError, REL.Refused, ValueError) as x:
        return [f'package B10/B12 pins: {type(x).__name__}: {x}']
    src = os.path.join(pkg, 'zavod', 'ops', 'server', 'probes')
    for n in PROGRAMS + UNITS:
        try:
            got = REL.sha_b(read(os.path.join(src, n)))
        except OSError as x:
            probs.append(f'package {n} {type(x).__name__}')
            continue
        if n in UNCHANGED:
            if n not in p10 or got != p10[n] or (n in p12 and got != p12[n]):
                probs.append(f'package {n} differs from B10/B12 pins')
        elif got != {**ACCEPTED_SHA, **UNIT_ACCEPTED_SHA}[n]:
            probs.append(f'package {n} differs from the accepted sum')
    return probs


def b12_installed_expected(pins):
    """INSTALLED.sha256 B12, собранный заново из отпечатков B12: 7 модулей, RELEASE и копия отпечатков B9 — строка
    «<sha256>  <путь>» на каждый, по пути (как B10.installed_bytes)."""
    lib = B12.LIB
    rel = f'commit={pins["release_commit"]}\nversion={B12_RELEASE_VERSION}\n'.encode('ascii')
    rows = [(os.path.join(lib, n), pins[n]) for n in B12.LIB_FILES]
    rows.append((os.path.join(lib, 'RELEASE'), REL.sha_b(rel)))
    rows.append((os.path.join(lib, PINS_B9_NAME), pins[PINS_B9_NAME]))
    return ''.join(f'{h}  {p}\n' for p, h in sorted(rows)).encode('ascii'), rel


def b12_problems(pkg):
    """B12 цел (только чтение; п. 3 б проекта, образец B12.b11_problems): папка — обычная папка root:root 0755 без лишних
    файлов (в том числе __pycache__); каждый из 10 файлов — обычный файл root:root 0644 с одной ссылкой и суммой из
    отпечатков B12; RELEASE — коммит выпуска B12; INSTALLED.sha256 — байт в байт список, собранный заново."""
    try:
        pins = pins12(pkg)
        want_list, want_rel = b12_installed_expected(pins)
    except (OSError, REL.Refused, ValueError) as x:
        return [f'B12 pins in the package: {type(x).__name__}: {x}']
    probs = []
    lib = B12.LIB
    files = {os.path.join(lib, k): (pins[k], B12.LIB_FILES[k]) for k in B12.LIB_FILES}
    files[os.path.join(lib, 'RELEASE')] = (REL.sha_b(want_rel), 0o644)
    files[os.path.join(lib, PINS_B9_NAME)] = (pins[PINS_B9_NAME], 0o644)
    files[os.path.join(lib, INSTALLED_NAME)] = (REL.sha_b(want_list), 0o644)
    try:
        st = os.lstat(lib)
        if not stat.S_ISDIR(st.st_mode):
            return [f'B12 {lib} is not a plain folder']
        if (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) != (REL.ROOT_UID, REL.ROOT_GID, 0o755):
            probs.append(f'B12 {lib} owner or mode differs from the B12 release')
        extra = sorted(set(os.listdir(lib)) - {os.path.basename(p) for p in files})
        if extra:
            probs.append(f'B12 {lib} holds other files: {extra[:5]}')
    except OSError as x:
        return [f'B12 {lib} {type(x).__name__}']
    for p, (h, mode) in sorted(files.items()):
        try:
            st = os.lstat(p)
        except OSError as x:
            probs.append(f'B12 {p} {type(x).__name__}')
            continue
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            probs.append(f'B12 {p} is not a plain single-link file')
        elif (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) != (REL.ROOT_UID, REL.ROOT_GID, mode):
            probs.append(f'B12 {p} owner or mode differs from the B12 release')
        elif REL.sha(p) != h:
            probs.append(f'B12 {p} differs from B12 pins')
    return probs


def common(pkg, rep):
    """Общий список B13: состав пакета, B8, B9 (с допуском байт-кода как в B10–B12), B10, B11, B12, службы (ничего не
    работает), учётная запись, журнал и отметки серий. Возвращает учётную запись zprobe или None."""
    p = pkg_problems(pkg)
    rep.add('PKG_MODULES', 'FAIL' if p else 'OK', '; '.join(p) or '-')
    p = B9.b8_problems(pkg)
    rep.add('B8', 'FAIL' if p else 'OK', '; '.join(p) or '-')
    p = B10.b9_problems(pkg)
    pyc = [] if p else B10.pycache_problems()[1]
    rep.add('B9', 'FAIL' if p else 'OK', '; '.join(p) or (
        f'- (B9 bytecode folder {B10.B9_PYCACHE}: {len(pyc)} .pyc of B9 modules, tolerated)' if pyc else '-'))
    p = B11.b10_problems(pkg)
    rep.add('B10', 'FAIL' if p else 'OK', '; '.join(p) or '-')
    p = B12.b11_problems(pkg)
    rep.add('B11', 'FAIL' if p else 'OK', '; '.join(p) or '-')
    p = b12_problems(pkg)
    rep.add('B12', 'FAIL' if p else 'OK', '; '.join(p) or '-')
    p = B9.units_problems()
    rep.add('UNITS', 'FAIL' if p else 'OK', '; '.join(p) or '-')
    p, zp = B9.account_problems()
    rep.add('ACCOUNT', 'FAIL' if p else 'OK', '; '.join(p) or f'uid={zp.pw_uid}')
    if zp is None:
        return None
    p, line = B9.journal_problems()
    rep.add('JOURNAL', 'FAIL' if p else 'OK', '; '.join(p) or line)
    p = B9.started_problems(zp)
    rep.add('STARTED', 'FAIL' if p else 'OK', '; '.join(p) or B9.KNOWN_SERIES)
    return zp


def unit_expect():
    """Свойства служб B13 (systemctl show): те же, что у B9/B10, имена — b13, папка программ — LIB, python3 -I -B."""
    def fix(v):
        if isinstance(v, str):
            return (v.replace('zprobe-journal-b9@', 'zprobe-journal-b13@').replace('zprobe-run-b9@', 'zprobe-run-b13@')
                    .replace(f'/usr/bin/python3 -I {LIB}/', f'/usr/bin/python3 -I -B {LIB}/'))
        if isinstance(v, list):
            return [tuple(fix(x) for x in t) for t in v]
        return v
    return {u: {k: fix(v) for k, v in want.items()} for u, want in B10._b9_unit_expect().items()}


def lib_extra_problems(tg):
    """В папке программ B13 ровно файлы целей — ни __pycache__, ни иного."""
    own = {os.path.basename(p) for p, _, _ in tg if os.path.dirname(p) == LIB}
    try:
        extra = sorted(set(os.listdir(LIB)) - own)
    except OSError as x:
        return [f'{LIB} {type(x).__name__}']
    return [f'{LIB} holds other files: {extra[:5]}'] if extra else []


def installed_problems(pkg):
    """INSTALLED.sha256 B13 = ожидаемый список (root, 0644, байт в байт); эталон файла службы — строка шаблона B13; каждый
    файл списка сейчас с той же суммой; в папке B13 нет лишнего."""
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
    return probs + lib_extra_problems(tg)


def verify_installed(pkg, rep):
    common(pkg, rep)
    bad = [f'{p}: {s}' for p, d, m in targets(pkg) for s in [B9.target_state(p, d, m)] if s != 'same']
    rep.add('TARGETS_SAME', 'FAIL' if bad else 'OK', '; '.join(bad) or '-')
    p = B9.show_problems()
    for _, full in p:                              # строка CHECK не длиннее 300 знаков — значения отдельно
        print('UNITS_LOADED_DETAIL ' + full, flush=True)
    rep.add('UNITS_LOADED', 'FAIL' if p else 'OK', '; '.join(s for s, _ in p) or '-')
    p = installed_problems(pkg) if not bad else []
    rep.add('INSTALLED_LIST', 'FAIL' if p else 'OK', '; '.join(p) or installed_path())


def preflight(pkg, rep):
    common(pkg, rep)
    tg = targets(pkg)
    there = [p for p, _, _ in tg if os.path.lexists(p)]
    rep.add('TARGETS_ABSENT', 'FAIL' if there else 'OK', ('present: ' + ', '.join(there)) if there else '-')
    p = B9.parent_problems(tg)
    rep.add('PARENTS', 'FAIL' if p else 'OK', '; '.join(sorted(set(p))) or '-')


def sync_dirs(tg):
    """Папки целей и родитель LIB — fsync после создания файлов (запись имён в папках на диске)."""
    for d in sorted({os.path.dirname(path) for path, _, _ in tg} | {os.path.dirname(LIB)}):
        fd = os.open(d, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def install(pkg, rep):
    """Как install B10: проверки, план B9-порядка, дневник, создание только новых целей B13 (папка LIB и две службы),
    fsync папок, daemon-reload, systemd-analyze verify, verify-installed. Сбой — PARTIAL с перечнем созданного, без
    удаления. Итог ZPROBE_B13_INSTALL."""
    lock = REL.install_lock()
    if lock is None:
        print('ZPROBE_B13_INSTALL=REFUSED another install is running; nothing changed')
        return 1
    try:
        zp = common(pkg, rep)
        tg = targets(pkg)
        p = B9.parent_problems(tg)
        rep.add('PARENTS', 'FAIL' if p else 'OK', '; '.join(sorted(set(p))) or '-')
        if rep.fails or zp is None:
            print(f'ZPROBE_B13_INSTALL=REFUSED checks fails={rep.fails}; nothing created')
            return 1
        acts, probs = B9.plan(pkg)
        if probs or not acts:
            for x in probs:
                print('CONFLICT ' + x)
            print('ZPROBE_B13_INSTALL=REFUSED ' + ('conflicts=%d' % len(probs) if probs else 'already installed')
                  + '; nothing created')
            return 1
        done = []
        os.umask(0o077)
        j = REL.Journal(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        try:
            REL.apply(acts, done, j)
            sync_dirs(tg)
        except Exception as x:  # noqa: BLE001
            print(f'ZPROBE_B13_INSTALL=PARTIAL STOP created={done} journal={j.path} error={type(x).__name__}: {x}; '
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
        print('ZPROBE_B13_INSTALL=' + ('OK' if ok else 'REFUSED installed state does not match; STOP, nothing removed'))
        return 0 if ok else 1
    finally:
        os.close(lock)


# Переменные и функции модуля B9 — на значения B13 (функции B9 берут их из своего модуля в момент вызова).
B9.LIB, B9.UNITS, B9.LIB_FILES, B9.UNIT_SHOW, B9.WATCH_UNITS = LIB, UNITS, LIB_FILES, UNIT_SHOW, WATCH_UNITS
B9.targets, B9.unit_expect, B9.common, B9.verify_installed = targets, unit_expect, common, verify_installed
REL.LIB = LIB
REL.JOURNAL_PREFIX = 'zprobe-install-3.5.5-b13-'
REL.TESTS = '/var/lib/zavod/probes-tests-b13'


def sync_paths():
    """Испытания меняют LIB и UNIT_DIR этого модуля — те же значения нужны модулям B9 и выпуска."""
    B9.LIB, B9.UNIT_DIR, REL.LIB = LIB, UNIT_DIR, LIB


def main():
    a = sys.argv[1:]
    modes = {'preflight': preflight, 'verify-installed': verify_installed}
    ok = os.geteuid() == 0 and ((len(a) == 2 and a[0] in ('preflight', 'verify-installed', 'install')) or
                                (len(a) == 3 and a[0] == 'report' and a[2] in modes))
    if not ok:
        print('usage (root): zprobe_release_b13.py preflight|verify-installed|install <package dir> | '
              'report <package dir> preflight|verify-installed')
        return 2
    pkg = os.path.abspath(a[1])
    rep = REL.Report()
    try:
        if a[0] == 'install':
            return install(pkg, rep)
        modes[a[2] if a[0] == 'report' else a[0]](pkg, rep)
    except Exception as x:  # noqa: BLE001 — всегда явный итог
        print(f'ZPROBE_B13_{a[0].upper()}=FAIL error={type(x).__name__}: {x}')
        return 1
    name = (a[2] if a[0] == 'report' else a[0]).upper().replace('-', '_')
    if a[0] == 'report':   # отчёт только в stdout, файла нет (как B12, REL112 M-01)
        text = ('\n'.join(rep.lines) + '\n').encode('utf-8')
        print(f'REPORT_SHA256={REL.sha_b(text)} lines={len(rep.lines)} '
              '(stdout only, no file written; diagnostics, not a permission)')
    print(f'ZPROBE_B13_{name}={"FAIL" if rep.fails else "OK"} fails={rep.fails}')
    return 1 if rep.fails else 0


if __name__ == '__main__':
    sys.exit(main())
