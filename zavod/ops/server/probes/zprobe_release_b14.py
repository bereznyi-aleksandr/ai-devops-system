#!/usr/bin/python3
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_release_b14.py
# ВЕРСИЯ: v0.1 (выпуск B14)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-18 22:09 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-18 22:09 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминал zavod (пускатель); автор, принять не может. Аудитор — ChatGPT.
# НАЗНАЧЕНИЕ: установка B14 рядом с B8, B9, B10, B11, B12 и B13 (REL139 AGREED: бегунок v0.18 — RUNNING сразу после start,
#   окно collect из бюджета сеанса; службы -b14@ с TimeoutStartSec 2700). Строится на zprobe_release_b13.py: его модуль (и
#   через него B12…B9) берётся целиком, здесь свои цели и своя проверка «B13 цел». Отличия от B13:
#   - папка программ /usr/local/lib/zavod/probes-b14 — ровно 14 файлов: 12 программ (тот же набор), RELEASE и
#     INSTALLED.sha256; ДВЕ НОВЫЕ СЛУЖБЫ /etc/systemd/system/zprobe-run-b14@.service и zprobe-journal-b14@.service, затем
#     daemon-reload и systemd-analyze verify (как B13); INSTALLED.sha256 — 15 строк (12 программ, RELEASE, обе службы);
#   - B8–B12 целы — проверками B13 (B12 — B13.b12_problems); B13 цел (только чтение): папка probes-b13 — обычная папка
#     root:root 0755, ровно 14 файлов (12 программ, RELEASE, INSTALLED.sha256), каждый — обычный файл root:root с одной
#     ссылкой (zprobe-start 0755, остальные 0644); программы — суммы из zprobe_pins_b13.txt пакета; RELEASE — байт в байт
#     «commit=<коммит B13>\nversion=3.5.5-b13\n»; INSTALLED.sha256 — байт в байт список, собранный заново из отпечатков
#     B13 (15 строк); две службы -b13@ — обычные файлы root:root 0644 с одной ссылкой и суммами из отпечатков B13;
#     посторонних файлов (в том числе __pycache__) в папке нет;
#   - файлы отпечатков B8–B13 в пакете обязаны иметь известные SHA-256 (B8–B12 — как zprobe_release_b13.PINS_FILE_SHA,
#     B13 — 75f15f58…), release_commit B13 — 0726d1bd4…;
#   - модули «без изменений» (pb1_session, zprobe_rules, zprobe_seal, zprobe_export, zprobe_dropin, zprobe_export_rules)
#     равны отпечаткам B13 (первые четыре — и B10/B12, как в B13); изменённые программы и обе службы — закреплённым суммам
#     ACCEPTED (иначе FAIL PKG_MODULES);
#   - журнал и отметки после серии pb1trial3: started — ровно pb1trial1, pb1trial2, pb1trial3; segments=3, seq=6; якорь —
#     digest b5076167…09aa и last_sha256 12e8a885…c9af из вывода серии pb1trial3 (снимок B3_SCREEN_END_20261118_2108.jpg,
#     B3_B4_B5_RESULT_DIAG.txt стр. 15 и 19, ответ REL138 стр. 37); preflight на сервере (только чтение) сверяет их до
#     установки — расхождение = FAIL JOURNAL, установки нет;
#   - дневник тот же (INTENT → CREATED → DONE, O_EXCL, fsync), префикс zprobe-install-3.5.5-b14-, папка испытаний
#     /var/lib/zavod/probes-tests-b14.
#   Режимы те же: preflight | verify-installed | install <пакет> | report <пакет> preflight|verify-installed.
#   install пишет только папку probes-b14 и две службы; любой сбой — итог PARTIAL с перечнем созданного (STOP), без
#   удаления (P4.702): повтор достраивает только объекты этого выпуска по дневнику.
# ОГРАНИЧЕНИЯ: B8–B13 только читаются; ничего не удаляется, не переименовывается и не перезаписывается. Модуль меняет
#   переменные zprobe_release_b9/b10 (targets, серии журнала и др.) и zprobe_release в своём процессе — не импортировать
#   вместе с установкой B9–B13 в одном процессе. SQL этот выпуск не ставит. Службы и их запуск — только после аудита
#   выпуска и «да» оператора.
import datetime
import os
import stat
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zprobe_release_b13 as B13  # noqa: E402

B12 = B13.B12
B11 = B13.B11
B10 = B13.B10
B9 = B13.B9
REL = B13.REL
UN = B13.UN

# пути — переменные модуля (испытания подменяют их на папку испытания; пути B8–B13 — в их модулях)
LIB = '/usr/local/lib/zavod/probes-b14'
UNIT_DIR = B9.UNIT_DIR
UNITS = ('zprobe-run-b14@.service', 'zprobe-journal-b14@.service')
PROGRAMS = B13.PROGRAMS
UNCHANGED = ('pb1_session.py', 'zprobe_rules.py', 'zprobe_seal.py', 'zprobe_export.py', 'zprobe_dropin.py',
             'zprobe_export_rules.py')
UNCHANGED_B10 = B13.UNCHANGED                                  # первые четыре — ещё и отпечатки B10/B12 (как в B13)
LIB_FILES = {n: (0o755 if n == 'zprobe-start' else 0o644) for n in PROGRAMS}
INSTALLED_NAME = B13.INSTALLED_NAME
PINS_B12_SRC = B13.PINS_B12_SRC
PINS_B13_SRC = os.path.join('zavod', 'ops', 'zprobe_pins_b13.txt')
B13_RELEASE_VERSION = '3.5.5-b13'
B13_RELEASE_COMMIT = '0726d1bd43bbb0dd9d70043ed8985d25c3ae99b9'
# Известные суммы файлов отпечатков B8–B12 (как у B13) и B13 (файл замороженного выпуска B13 917893350).
PINS_FILE_SHA = dict(B13.PINS_FILE_SHA)
PINS_FILE_SHA[PINS_B13_SRC] = '75f15f58683d71e4d37873dda268cb710138cb131e7c188d247f3efc4a665fe9'
# Закреплённые суммы (те же, что build_release_3_5_5_b14.ACCEPTED; для двух служб — свои): байты коммита ae75fcdc3.
# Другие байты — FAIL PKG_MODULES, новый код без нового аудита не пройдёт.
ACCEPTED_SHA = {'zprobe_runner.py': '65ebe655f314fa00f6bc4fbbd405dc9855d019c136a4fa3ca653aeed9f56e54a',
                'zprobe_checks.py': '52881660359594df0ea19c26ee3af43bf19df3f08e4a4c9d3b1a8d79e016d7ab',
                'zprobe_journal.py': '0b9143992d269a5db903549c4683877f8dffdf8bfed696c6cc6f572831bf0251',
                'zprobe-start': '528c7ab7c7237c188c817fbc86401c7814215e504759b97cdc64473771c042b3',
                'zprobe_unstarted.py': 'e21d7ba4fc8db894a2b89bd6d46fb5aa800a9f35c04567c51de02ec9f1954cac',
                'zevidence_send.py': '0b1e7e28f5fc5dda7529fd58195e9e82462c1aaf9b81bd1064e93dd8aad9ad01'}
UNIT_ACCEPTED_SHA = {'zprobe-run-b14@.service': '7ac28b2a9660fadb1b993a467e6a7a2d29179e85c7a74a7f605d72e31723d934',
                     'zprobe-journal-b14@.service': '562950539f86e8bef094b028da2e03f3633e14c36804fba9bcd57975a6dc42df'}
# Ключи отпечатков B13 (zavod/ops/zprobe_pins_b13.txt) — строгий разбор: ровно эти 24 и release_commit.
B13_PIN_KEYS = (B13.PROGRAMS + B13.UNITS + ('zagent@.service', 'zavod-proxy', 'zavod-gate', 'zavod-egress.nft')
                + ('phone_zprobe_series_b13.sh', 'phone_zprobe_verify.py', 'phone_zprobe_rules.py')
                + ('pc_zprobe_refs.sh', 'pc_zprobe_refs_check.py', 'pc_zprobe_rules.py'))
UNIT_SHOW = ('zprobe-journal-b14@check.service', 'zprobe-run-b14@check.service')
WATCH_UNITS = tuple(B13.WATCH_UNITS) + ('zprobe-run-b14@*', 'zprobe-journal-b14@*')
# Журнал после серии pb1trial3 (сегмент 000003.jsonl — pb1trial3, по порядку STARTED_SERIES).
STARTED_SERIES = ('pb1trial1', 'pb1trial2', 'pb1trial3')
KNOWN_SERIES = ','.join(STARTED_SERIES)
EXPECT_SEGMENTS, EXPECT_SEQ = 3, 6
EXPECT_DIGEST = 'b5076167ddd30841190681acdea5e08737108a89f05e3bbd6f3afbf4981a09aa'  # anchor=3:… вывода серии pb1trial3
EXPECT_LAST = '12e8a8858f32f6cda65f34c5535222dc3dc73223e377a9eb084531da8891c9af'    # last_sha256 seq=6 там же


def installed_path():
    return os.path.join(LIB, INSTALLED_NAME)


def template_path():
    """Эталон файла службы B14 — этот путь и его сумма в INSTALLED.sha256 (zprobe_unstarted.expected_fragment)."""
    return os.path.join(UNIT_DIR, UNITS[0])


def read(path):
    with open(path, 'rb') as f:
        return f.read()


def pins13(pkg):
    """Отпечатки B13 из пакета: строгий разбор (24 ключа) и коммит выпуска B13 (иначе REL.Refused)."""
    pins = B9.read_pins_file(os.path.join(pkg, PINS_B13_SRC), B13_PIN_KEYS)
    if pins['release_commit'] != B13_RELEASE_COMMIT:
        raise REL.Refused(f'zprobe_pins_b13.txt: release_commit {pins["release_commit"]} is not B13 {B13_RELEASE_COMMIT}')
    return pins


def targets(pkg):
    """Цели B14: (путь, байты, права); первой — папка LIB; затем 12 программ, RELEASE, две службы и последней —
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
    """Состав пакета: шесть файлов отпечатков — известные суммы; отпечатки B12 и B13 — их коммиты; модули «без
    изменений» равны отпечаткам B13 (первые четыре — и B10/B12); изменённые программы и обе службы — суммам ACCEPTED."""
    probs = []
    for rel, want in sorted(PINS_FILE_SHA.items()):
        try:
            got = REL.sha_b(read(os.path.join(pkg, rel)))
        except OSError as x:
            probs.append(f'package {rel} {type(x).__name__}')
            continue
        if got != want:
            probs.append(f'package {rel} differs from the known B8-B13 release sum')
    if probs:
        return probs
    try:
        p10 = B11.pins10(pkg)
        p12 = B13.pins12(pkg)
        p13 = pins13(pkg)
    except (OSError, REL.Refused, ValueError) as x:
        return [f'package B10/B12/B13 pins: {type(x).__name__}: {x}']
    src = os.path.join(pkg, 'zavod', 'ops', 'server', 'probes')
    for n in PROGRAMS + UNITS:
        try:
            got = REL.sha_b(read(os.path.join(src, n)))
        except OSError as x:
            probs.append(f'package {n} {type(x).__name__}')
            continue
        if n in UNCHANGED:
            old = n in UNCHANGED_B10 and (n not in p10 or got != p10[n] or (n in p12 and got != p12[n]))
            if old or got != p13.get(n):
                probs.append(f'package {n} differs from B13 (B10/B12) pins')
        elif got != {**ACCEPTED_SHA, **UNIT_ACCEPTED_SHA}[n]:
            probs.append(f'package {n} differs from the accepted sum')
    return probs


def b13_installed_expected(pins):
    """INSTALLED.sha256 B13, собранный заново из отпечатков B13: 12 программ, RELEASE и две службы -b13@ — строка
    «<sha256>  <путь>» на каждый, по пути (как B10.installed_bytes)."""
    lib = B13.LIB
    rel = f'commit={pins["release_commit"]}\nversion={B13_RELEASE_VERSION}\n'.encode('ascii')
    rows = [(os.path.join(lib, n), pins[n]) for n in B13.LIB_FILES]
    rows.append((os.path.join(lib, 'RELEASE'), REL.sha_b(rel)))
    rows += [(os.path.join(B13.UNIT_DIR, u), pins[u]) for u in B13.UNITS]
    return ''.join(f'{h}  {p}\n' for p, h in sorted(rows)).encode('ascii'), rel


def b13_problems(pkg):
    """B13 цел (только чтение; образец B13.b12_problems): папка — обычная папка root:root 0755 без лишних файлов (в том
    числе __pycache__); каждый из 14 файлов — обычный файл root:root с одной ссылкой, правами выпуска B13 и суммой из
    отпечатков B13; RELEASE — коммит выпуска B13; INSTALLED.sha256 — байт в байт список, собранный заново; две службы
    -b13@ — обычные файлы root:root 0644 с одной ссылкой и суммами отпечатков B13."""
    try:
        pins = pins13(pkg)
        want_list, want_rel = b13_installed_expected(pins)
    except (OSError, REL.Refused, ValueError) as x:
        return [f'B13 pins in the package: {type(x).__name__}: {x}']
    probs = []
    lib = B13.LIB
    files = {os.path.join(lib, k): (pins[k], B13.LIB_FILES[k]) for k in B13.LIB_FILES}
    files[os.path.join(lib, 'RELEASE')] = (REL.sha_b(want_rel), 0o644)
    files[os.path.join(lib, INSTALLED_NAME)] = (REL.sha_b(want_list), 0o644)
    try:
        st = os.lstat(lib)
        if not stat.S_ISDIR(st.st_mode):
            return [f'B13 {lib} is not a plain folder']
        if (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) != (REL.ROOT_UID, REL.ROOT_GID, 0o755):
            probs.append(f'B13 {lib} owner or mode differs from the B13 release')
        extra = sorted(set(os.listdir(lib)) - {os.path.basename(p) for p in files})
        if extra:
            probs.append(f'B13 {lib} holds other files: {extra[:5]}')
    except OSError as x:
        return [f'B13 {lib} {type(x).__name__}']
    for u in B13.UNITS:
        files[os.path.join(B13.UNIT_DIR, u)] = (pins[u], 0o644)
    for p, (h, mode) in sorted(files.items()):
        try:
            st = os.lstat(p)
        except OSError as x:
            probs.append(f'B13 {p} {type(x).__name__}')
            continue
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            probs.append(f'B13 {p} is not a plain single-link file')
        elif (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) != (REL.ROOT_UID, REL.ROOT_GID, mode):
            probs.append(f'B13 {p} owner or mode differs from the B13 release')
        elif REL.sha(p) != h:
            probs.append(f'B13 {p} differs from B13 pins')
    return probs


_b10_journal_problems = B10._b9_journal_problems


def journal_problems():
    """Шлюз журнала B9 (только чтение) с якорем после pb1trial3; текст замечания — про pb1trial3."""
    probs, line = _b10_journal_problems()
    return [p.replace('after pb1trial1', 'after pb1trial3') for p in probs], line


def common(pkg, rep):
    """Общий список B14: состав пакета, B8, B9 (с допуском байт-кода как в B10–B13), B10, B11, B12, B13, службы (ничего
    не работает), учётная запись, журнал и отметки трёх серий. Возвращает учётную запись zprobe или None."""
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
    p = B13.b12_problems(pkg)
    rep.add('B12', 'FAIL' if p else 'OK', '; '.join(p) or '-')
    p = b13_problems(pkg)
    rep.add('B13', 'FAIL' if p else 'OK', '; '.join(p) or '-')
    p = B9.units_problems()
    rep.add('UNITS', 'FAIL' if p else 'OK', '; '.join(p) or '-')
    p, zp = B9.account_problems()
    rep.add('ACCOUNT', 'FAIL' if p else 'OK', '; '.join(p) or f'uid={zp.pw_uid}')
    if zp is None:
        return None
    p, line = B9.journal_problems()
    rep.add('JOURNAL', 'FAIL' if p else 'OK', '; '.join(p) or line)
    p = B9.started_problems(zp)
    rep.add('STARTED', 'FAIL' if p else 'OK', '; '.join(p) or KNOWN_SERIES)
    return zp


def unit_expect():
    """Свойства служб B14 (systemctl show): те же, что у B9/B10, имена — b14, папка программ — LIB, python3 -I -B."""
    def fix(v):
        if isinstance(v, str):
            return (v.replace('zprobe-journal-b9@', 'zprobe-journal-b14@').replace('zprobe-run-b9@', 'zprobe-run-b14@')
                    .replace(f'/usr/bin/python3 -I {LIB}/', f'/usr/bin/python3 -I -B {LIB}/'))
        if isinstance(v, list):
            return [tuple(fix(x) for x in t) for t in v]
        return v
    return {u: {k: fix(v) for k, v in want.items()} for u, want in B10._b9_unit_expect().items()}


def lib_extra_problems(tg):
    """В папке программ B14 ровно файлы целей — ни __pycache__, ни иного."""
    own = {os.path.basename(p) for p, _, _ in tg if os.path.dirname(p) == LIB}
    try:
        extra = sorted(set(os.listdir(LIB)) - own)
    except OSError as x:
        return [f'{LIB} {type(x).__name__}']
    return [f'{LIB} holds other files: {extra[:5]}'] if extra else []


def installed_problems(pkg):
    """INSTALLED.sha256 B14 = ожидаемый список (root, 0644, байт в байт); эталон файла службы — строка шаблона B14; каждый
    файл списка сейчас с той же суммой; в папке B14 нет лишнего."""
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
    """Как install B13: проверки, план B9-порядка, дневник, создание только новых целей B14 (папка LIB и две службы),
    fsync папок, daemon-reload, systemd-analyze verify, verify-installed. Сбой — PARTIAL с перечнем созданного, без
    удаления. Итог ZPROBE_B14_INSTALL."""
    lock = REL.install_lock()
    if lock is None:
        print('ZPROBE_B14_INSTALL=REFUSED another install is running; nothing changed')
        return 1
    try:
        zp = common(pkg, rep)
        tg = targets(pkg)
        p = B9.parent_problems(tg)
        rep.add('PARENTS', 'FAIL' if p else 'OK', '; '.join(sorted(set(p))) or '-')
        if rep.fails or zp is None:
            print(f'ZPROBE_B14_INSTALL=REFUSED checks fails={rep.fails}; nothing created')
            return 1
        acts, probs = B9.plan(pkg)
        if probs or not acts:
            for x in probs:
                print('CONFLICT ' + x)
            print('ZPROBE_B14_INSTALL=REFUSED ' + ('conflicts=%d' % len(probs) if probs else 'already installed')
                  + '; nothing created')
            return 1
        done = []
        os.umask(0o077)
        j = REL.Journal(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        try:
            REL.apply(acts, done, j)
            sync_dirs(tg)
        except Exception as x:  # noqa: BLE001
            print(f'ZPROBE_B14_INSTALL=PARTIAL STOP created={done} journal={j.path} error={type(x).__name__}: {x}; '
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
        print('ZPROBE_B14_INSTALL=' + ('OK' if ok else 'REFUSED installed state does not match; STOP, nothing removed'))
        return 0 if ok else 1
    finally:
        os.close(lock)


# Переменные и функции модулей B9 и B10 — на значения B14 (их функции берут их из своего модуля в момент вызова).
B9.LIB, B9.UNITS, B9.LIB_FILES, B9.UNIT_SHOW, B9.WATCH_UNITS = LIB, UNITS, LIB_FILES, UNIT_SHOW, WATCH_UNITS
B9.KNOWN_SERIES, B9.EXPECT_SEGMENTS, B9.EXPECT_SEQ = KNOWN_SERIES, EXPECT_SEGMENTS, EXPECT_SEQ
B9.EXPECT_DIGEST, B9.EXPECT_LAST = EXPECT_DIGEST, EXPECT_LAST
B10.STARTED_SERIES, B10.KNOWN_SERIES = STARTED_SERIES, KNOWN_SERIES
B9.targets, B9.unit_expect, B9.common, B9.verify_installed = targets, unit_expect, common, verify_installed
B9.journal_problems = journal_problems
REL.LIB = LIB
REL.JOURNAL_PREFIX = 'zprobe-install-3.5.5-b14-'
REL.TESTS = '/var/lib/zavod/probes-tests-b14'


def sync_paths():
    """Испытания меняют LIB и UNIT_DIR этого модуля — те же значения нужны модулям B9 и выпуска."""
    B9.LIB, B9.UNIT_DIR, REL.LIB = LIB, UNIT_DIR, LIB


def main():
    a = sys.argv[1:]
    modes = {'preflight': preflight, 'verify-installed': verify_installed}
    ok = os.geteuid() == 0 and ((len(a) == 2 and a[0] in ('preflight', 'verify-installed', 'install')) or
                                (len(a) == 3 and a[0] == 'report' and a[2] in modes))
    if not ok:
        print('usage (root): zprobe_release_b14.py preflight|verify-installed|install <package dir> | '
              'report <package dir> preflight|verify-installed')
        return 2
    pkg = os.path.abspath(a[1])
    rep = REL.Report()
    try:
        if a[0] == 'install':
            return install(pkg, rep)
        modes[a[2] if a[0] == 'report' else a[0]](pkg, rep)
    except Exception as x:  # noqa: BLE001 — всегда явный итог
        print(f'ZPROBE_B14_{a[0].upper()}=FAIL error={type(x).__name__}: {x}')
        return 1
    name = (a[2] if a[0] == 'report' else a[0]).upper().replace('-', '_')
    if a[0] == 'report':   # отчёт только в stdout, файла нет (как B12, REL112 M-01)
        text = ('\n'.join(rep.lines) + '\n').encode('utf-8')
        print(f'REPORT_SHA256={REL.sha_b(text)} lines={len(rep.lines)} '
              '(stdout only, no file written; diagnostics, not a permission)')
    print(f'ZPROBE_B14_{name}={"FAIL" if rep.fails else "OK"} fails={rep.fails}')
    return 1 if rep.fails else 0


if __name__ == '__main__':
    sys.exit(main())
