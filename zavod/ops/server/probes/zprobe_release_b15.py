#!/usr/bin/python3
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_release_b15.py
# ВЕРСИЯ: v0.2 (выпуск B15)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-19 14:38 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 16:10 +02:00
# v0.2 (REL156 L-355-REL156-01): суммы pb1_session.py v1.1 и zprobe_rules.py v0.15 (правка только текста окна).
# ИСПОЛНИТЕЛЬ: Claude, терминал zavod (пускатель); автор, принять не может. Аудитор — ChatGPT.
# НАЗНАЧЕНИЕ: установка B15 рядом с B8–B14 (REL155 AGREED: связь git push с отказом ядра, записи старта startrec,
#   zprobe-start с --status; службы -b15@ — копии -b14@ с именами B15). Строится на zprobe_release_b14.py: его модуль (и
#   через него B13…B9) берётся целиком, здесь свои цели и своя проверка «B14 цел». Отличия от B14:
#   - папка программ /usr/local/lib/zavod/probes-b15 — ровно 16 файлов: 14 программ (12 программ B14 и два модуля,
#     которые импортируют бегунок, журнал и zprobe-start: zprobe_start_status.py и zprobe_recstore.py), RELEASE и
#     INSTALLED.sha256; две новые службы /etc/systemd/system/zprobe-run-b15@.service и zprobe-journal-b15@.service, затем
#     daemon-reload и systemd-analyze verify (как B14); INSTALLED.sha256 — 17 строк (14 программ, RELEASE, обе службы);
#   - B8–B13 целы — проверками B14 (B13 — B14.b13_problems, B12 — B13.b12_problems); B14 цел (только чтение): папка
#     probes-b14 — обычная папка root:root 0755, ровно 14 файлов (12 программ, RELEASE, INSTALLED.sha256), каждый —
#     обычный файл root:root с одной ссылкой (zprobe-start 0755, остальные 0644); программы — суммы из
#     zprobe_pins_b14.txt пакета; RELEASE — байт в байт «commit=<коммит B14>\nversion=3.5.5-b14\n»; INSTALLED.sha256 —
#     байт в байт список, собранный заново из отпечатков B14 (15 строк); две службы -b14@ — обычные файлы root:root 0644
#     с одной ссылкой и суммами из отпечатков B14; посторонних файлов (в том числе __pycache__) в папке нет;
#   - файлы отпечатков B8–B14 в пакете обязаны иметь известные SHA-256 (B8–B13 — как zprobe_release_b14.PINS_FILE_SHA,
#     B14 — f6da444f…), release_commit B14 — 3a0f20680…;
#   - модули «без изменений» (zprobe_seal, zprobe_export, zprobe_dropin, zprobe_export_rules) равны отпечаткам B14;
#     изменённые и новые программы (10) и обе службы — закреплённым суммам ACCEPTED (иначе FAIL PKG_MODULES);
#   - журнал и отметки после серии pb1trial4: started — ровно pb1trial1…pb1trial4; segments=4, seq=62; digest
#     305e4933…ba51 — строка итога серии pb1trial4 на телефоне (verdict.txt «anchor=4:305e4933…»); seq и last_sha256
#     32273318…5d38 — посчитаны тем же R.journal_chain по полученной копии журнала (refetch1, четыре сегмента; digest
#     копии равен digest телефона); preflight на сервере (только чтение) сверяет их до установки — расхождение = FAIL
#     JOURNAL, установки нет;
#   - строка STARTREC (только чтение): папки записей старта /var/lib/zavod/probes/startrec ещё нет (её создаёт
#     zprobe-start первой серии B15: root:zprobe 0750) или это обычная папка root:zprobe 0750; иное — FAIL, установки нет;
#   - дневник тот же (INTENT → CREATED → DONE, O_EXCL, fsync), префикс zprobe-install-3.5.5-b15-, папка испытаний
#     /var/lib/zavod/probes-tests-b15.
#   Режимы те же: preflight | verify-installed | install <пакет> | report <пакет> preflight|verify-installed.
#   install пишет только папку probes-b15 и две службы; любой сбой — итог PARTIAL с перечнем созданного (STOP), без
#   удаления (P4.702): повтор достраивает только объекты этого выпуска по дневнику.
# ОГРАНИЧЕНИЯ: B8–B14 только читаются; ничего не удаляется, не переименовывается и не перезаписывается. Папку startrec
#   установщик не создаёт. Модуль меняет переменные zprobe_release_b9/b10 (targets, серии журнала и др.) и
#   zprobe_release в своём процессе — не импортировать вместе с установкой B9–B14 в одном процессе. SQL этот выпуск не
#   ставит. Службы и их запуск — только после аудита выпуска и «да» оператора.
import datetime
import os
import stat
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zprobe_release_b14 as B14  # noqa: E402

B13 = B14.B13
B12 = B14.B12
B11 = B14.B11
B10 = B14.B10
B9 = B14.B9
REL = B14.REL
UN = B14.UN

# пути — переменные модуля (испытания подменяют их на папку испытания; пути B8–B14 — в их модулях)
LIB = '/usr/local/lib/zavod/probes-b15'
UNIT_DIR = B9.UNIT_DIR
UNITS = ('zprobe-run-b15@.service', 'zprobe-journal-b15@.service')
PROGRAMS = B14.PROGRAMS + ('zprobe_start_status.py', 'zprobe_recstore.py')
UNCHANGED = ('zprobe_seal.py', 'zprobe_export.py', 'zprobe_dropin.py', 'zprobe_export_rules.py')   # байт в байт B14
LIB_FILES = {n: (0o755 if n == 'zprobe-start' else 0o644) for n in PROGRAMS}
INSTALLED_NAME = B14.INSTALLED_NAME
PINS_B12_SRC = B14.PINS_B12_SRC
PINS_B13_SRC = B14.PINS_B13_SRC
PINS_B14_SRC = os.path.join('zavod', 'ops', 'zprobe_pins_b14.txt')
B14_RELEASE_VERSION = '3.5.5-b14'
B14_RELEASE_COMMIT = '3a0f20680119ed858ce2ee17a865840eab2a63bb'
# Известные суммы файлов отпечатков B8–B13 (как у B14) и B14 (файл замороженного выпуска B14 43451be79).
PINS_FILE_SHA = dict(B14.PINS_FILE_SHA)
PINS_FILE_SHA[PINS_B14_SRC] = 'f6da444f8e158dada92243139b9286eb70ca1e9aa4110ddd5414e0aeea36fc40'
# Закреплённые суммы (те же, что build_release_3_5_5_b15.ACCEPTED; для двух служб — свои): байты ветки B15 после
# REL155 AGREED, принимает раунд REL156. Другие байты — FAIL PKG_MODULES, новый код без нового аудита не пройдёт.
ACCEPTED_SHA = {'pb1_session.py': '5ea2e34af5bb7bb76de1db571cd27bf374e67e10e8b62b974e3f740d28815082',
                'zprobe_rules.py': '073040060b1dccda6646bb835ef9f7ea05f9d213d736d0d854e896923dd9e842',
                'zprobe_runner.py': 'cda0590b22d2a5dd9065adf15c90141013a791a3c1954ddb87794d16cd9dad22',
                'zprobe_checks.py': '8d254bc2de769630240a2515bffac17520daf438f2faa3096b5d9b0ccfaecbc0',
                'zprobe_journal.py': 'd85aa8d3ad228f983a8c8f21237342e29c03efb566374302a108cbf8159d1083',
                'zprobe-start': 'c809654c645140261c43f10503b2c7135961e15edc0347e6cb3f5ed50f0affc7',
                'zprobe_unstarted.py': '182f0f4ab3d3a855e491f6546a47e026f70cf4df93fc2c76528a2b51e84c6528',
                'zevidence_send.py': '24a2d87e45ddb13ad077bd255e2273f404b4bc15254f8deb37587bcf3237232e',
                'zprobe_start_status.py': '829bcfc5591c7b22f212ac17d8c863aa5a38b5d9c5d19b15a3c014c2692ddf92',
                'zprobe_recstore.py': '81d9295dae0a6bfca49d507e87dba31adefbf0f8e948c165b42eb0465f19d6b1'}
UNIT_ACCEPTED_SHA = {'zprobe-run-b15@.service': 'a1b00b5d26bd5d8e26a3d656994b9a3091d11c59a7965937f08f0aa8b71e40aa',
                     'zprobe-journal-b15@.service': '8a4b61a5da496fef87691c818f093ebf3d468dc236be5f925af37114e89122e4'}
assert set(ACCEPTED_SHA) | set(UNCHANGED) == set(PROGRAMS) and not set(ACCEPTED_SHA) & set(UNCHANGED), 'program split'
# Ключи отпечатков B14 (zavod/ops/zprobe_pins_b14.txt) — строгий разбор: ровно эти 24 и release_commit.
B14_PIN_KEYS = (B14.PROGRAMS + B14.UNITS + ('zagent@.service', 'zavod-proxy', 'zavod-gate', 'zavod-egress.nft')
                + ('phone_zprobe_series_b14.sh', 'phone_zprobe_verify.py', 'phone_zprobe_rules.py')
                + ('pc_zprobe_refs.sh', 'pc_zprobe_refs_check.py', 'pc_zprobe_rules.py'))
UNIT_SHOW = ('zprobe-journal-b15@check.service', 'zprobe-run-b15@check.service')
WATCH_UNITS = tuple(B14.WATCH_UNITS) + ('zprobe-run-b15@*', 'zprobe-journal-b15@*')
# Журнал после серии pb1trial4 (сегмент 000004.jsonl — pb1trial4, по порядку STARTED_SERIES).
STARTED_SERIES = ('pb1trial1', 'pb1trial2', 'pb1trial3', 'pb1trial4')
KNOWN_SERIES = ','.join(STARTED_SERIES)
EXPECT_SEGMENTS, EXPECT_SEQ = 4, 62
EXPECT_DIGEST = '305e4933389b5f833a60bef9e421174b365d604534271c0da0f63d28e046ba51'  # anchor=4:… итога серии pb1trial4
EXPECT_LAST = '32273318589a5ed65074e0aac49aa510653f15c2099432f5f461666d30ec5d38'    # last_sha256 seq=62 копии журнала
STARTREC_NAME = 'startrec'   # папка записей старта в DATA модуля B9 (создаёт zprobe-start первой серии B15)


def installed_path():
    return os.path.join(LIB, INSTALLED_NAME)


def template_path():
    """Эталон файла службы B15 — этот путь и его сумма в INSTALLED.sha256 (zprobe_unstarted.expected_fragment)."""
    return os.path.join(UNIT_DIR, UNITS[0])


def read(path):
    with open(path, 'rb') as f:
        return f.read()


def pins14(pkg):
    """Отпечатки B14 из пакета: строгий разбор (24 ключа) и коммит выпуска B14 (иначе REL.Refused)."""
    pins = B9.read_pins_file(os.path.join(pkg, PINS_B14_SRC), B14_PIN_KEYS)
    if pins['release_commit'] != B14_RELEASE_COMMIT:
        raise REL.Refused(f'zprobe_pins_b14.txt: release_commit {pins["release_commit"]} is not B14 {B14_RELEASE_COMMIT}')
    return pins


def targets(pkg):
    """Цели B15: (путь, байты, права); первой — папка LIB; затем 12 программ, RELEASE, две службы и последней —
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
    """Состав пакета: семь файлов отпечатков — известные суммы; отпечатки B12, B13 и B14 — их коммиты; модули «без
    изменений» равны отпечаткам B14; изменённые и новые программы и обе службы — суммам ACCEPTED."""
    probs = []
    for rel, want in sorted(PINS_FILE_SHA.items()):
        try:
            got = REL.sha_b(read(os.path.join(pkg, rel)))
        except OSError as x:
            probs.append(f'package {rel} {type(x).__name__}')
            continue
        if got != want:
            probs.append(f'package {rel} differs from the known B8-B14 release sum')
    if probs:
        return probs
    try:
        B11.pins10(pkg)
        B13.pins12(pkg)
        B14.pins13(pkg)
        p14 = pins14(pkg)
    except (OSError, REL.Refused, ValueError) as x:
        return [f'package B10/B12/B13/B14 pins: {type(x).__name__}: {x}']
    src = os.path.join(pkg, 'zavod', 'ops', 'server', 'probes')
    for n in PROGRAMS + UNITS:
        try:
            got = REL.sha_b(read(os.path.join(src, n)))
        except OSError as x:
            probs.append(f'package {n} {type(x).__name__}')
            continue
        if n in UNCHANGED:
            if got != p14.get(n):
                probs.append(f'package {n} differs from B14 pins')
        elif got != {**ACCEPTED_SHA, **UNIT_ACCEPTED_SHA}[n]:
            probs.append(f'package {n} differs from the accepted sum')
    return probs


def b14_installed_expected(pins):
    """INSTALLED.sha256 B14, собранный заново из отпечатков B14: 12 программ, RELEASE и две службы -b14@ — строка
    «<sha256>  <путь>» на каждый, по пути (как B10.installed_bytes)."""
    lib = B14.LIB
    rel = f'commit={pins["release_commit"]}\nversion={B14_RELEASE_VERSION}\n'.encode('ascii')
    rows = [(os.path.join(lib, n), pins[n]) for n in B14.LIB_FILES]
    rows.append((os.path.join(lib, 'RELEASE'), REL.sha_b(rel)))
    rows += [(os.path.join(B14.UNIT_DIR, u), pins[u]) for u in B14.UNITS]
    return ''.join(f'{h}  {p}\n' for p, h in sorted(rows)).encode('ascii'), rel


def b14_problems(pkg):
    """B14 цел (только чтение; образец B14.b12_problems): папка — обычная папка root:root 0755 без лишних файлов (в том
    числе __pycache__); каждый из 14 файлов — обычный файл root:root с одной ссылкой, правами выпуска B14 и суммой из
    отпечатков B14; RELEASE — коммит выпуска B14; INSTALLED.sha256 — байт в байт список, собранный заново; две службы
    -b14@ — обычные файлы root:root 0644 с одной ссылкой и суммами отпечатков B14."""
    try:
        pins = pins14(pkg)
        want_list, want_rel = b14_installed_expected(pins)
    except (OSError, REL.Refused, ValueError) as x:
        return [f'B14 pins in the package: {type(x).__name__}: {x}']
    probs = []
    lib = B14.LIB
    files = {os.path.join(lib, k): (pins[k], B14.LIB_FILES[k]) for k in B14.LIB_FILES}
    files[os.path.join(lib, 'RELEASE')] = (REL.sha_b(want_rel), 0o644)
    files[os.path.join(lib, INSTALLED_NAME)] = (REL.sha_b(want_list), 0o644)
    try:
        st = os.lstat(lib)
        if not stat.S_ISDIR(st.st_mode):
            return [f'B14 {lib} is not a plain folder']
        if (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) != (REL.ROOT_UID, REL.ROOT_GID, 0o755):
            probs.append(f'B14 {lib} owner or mode differs from the B14 release')
        extra = sorted(set(os.listdir(lib)) - {os.path.basename(p) for p in files})
        if extra:
            probs.append(f'B14 {lib} holds other files: {extra[:5]}')
    except OSError as x:
        return [f'B14 {lib} {type(x).__name__}']
    for u in B14.UNITS:
        files[os.path.join(B14.UNIT_DIR, u)] = (pins[u], 0o644)
    for p, (h, mode) in sorted(files.items()):
        try:
            st = os.lstat(p)
        except OSError as x:
            probs.append(f'B14 {p} {type(x).__name__}')
            continue
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            probs.append(f'B14 {p} is not a plain single-link file')
        elif (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) != (REL.ROOT_UID, REL.ROOT_GID, mode):
            probs.append(f'B14 {p} owner or mode differs from the B14 release')
        elif REL.sha(p) != h:
            probs.append(f'B14 {p} differs from B14 pins')
    return probs


_b10_journal_problems = B10._b9_journal_problems


def journal_problems():
    """Шлюз журнала B9 (только чтение) с якорем после pb1trial4; текст замечания — про pb1trial4."""
    probs, line = _b10_journal_problems()
    return [p.replace('after pb1trial1', 'after pb1trial4') for p in probs], line


def startrec_problems(zp):
    """Папка записей старта: нет вовсе (её создаст zprobe-start первой серии) или обычная папка root:zprobe 0750."""
    p = os.path.join(B9.DATA, STARTREC_NAME)
    try:
        st = os.lstat(p)
    except FileNotFoundError:
        return [], f'{p} absent (zprobe-start of the first B15 series creates it root:zprobe 0750)'
    except OSError as x:
        return [f'{p} {type(x).__name__}'], ''
    if not stat.S_ISDIR(st.st_mode):
        return [f'{p} is not a plain folder'], ''
    if (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) != (REL.ROOT_UID, zp.pw_gid, 0o750):
        return [f'{p} owner or mode is not root:zprobe 0750'], ''
    return [], f'{p} root:zprobe 0750'


def common(pkg, rep):
    """Общий список B15: состав пакета, B8, B9 (с допуском байт-кода как в B10–B14), B10, B11, B12, B13, B14, службы
    (ничего не работает), учётная запись, журнал и отметки четырёх серий, папка startrec. Возвращает zprobe или None."""
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
    p = B14.b13_problems(pkg)
    rep.add('B13', 'FAIL' if p else 'OK', '; '.join(p) or '-')
    p = b14_problems(pkg)
    rep.add('B14', 'FAIL' if p else 'OK', '; '.join(p) or '-')
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
    p, line = startrec_problems(zp)
    rep.add('STARTREC', 'FAIL' if p else 'OK', '; '.join(p) or line)
    return zp


def unit_expect():
    """Свойства служб B15 (systemctl show): те же, что у B9/B10, имена — b15, папка программ — LIB, python3 -I -B."""
    def fix(v):
        if isinstance(v, str):
            return (v.replace('zprobe-journal-b9@', 'zprobe-journal-b15@').replace('zprobe-run-b9@', 'zprobe-run-b15@')
                    .replace(f'/usr/bin/python3 -I {LIB}/', f'/usr/bin/python3 -I -B {LIB}/'))
        if isinstance(v, list):
            return [tuple(fix(x) for x in t) for t in v]
        return v
    return {u: {k: fix(v) for k, v in want.items()} for u, want in B10._b9_unit_expect().items()}


def lib_extra_problems(tg):
    """В папке программ B15 ровно файлы целей — ни __pycache__, ни иного."""
    own = {os.path.basename(p) for p, _, _ in tg if os.path.dirname(p) == LIB}
    try:
        extra = sorted(set(os.listdir(LIB)) - own)
    except OSError as x:
        return [f'{LIB} {type(x).__name__}']
    return [f'{LIB} holds other files: {extra[:5]}'] if extra else []


def installed_problems(pkg):
    """INSTALLED.sha256 B15 = ожидаемый список (root, 0644, байт в байт); эталон файла службы — строка шаблона B15; каждый
    файл списка сейчас с той же суммой; в папке B15 нет лишнего."""
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
    """Как install B14: проверки, план B9-порядка, дневник, создание только новых целей B15 (папка LIB и две службы),
    fsync папок, daemon-reload, systemd-analyze verify, verify-installed. Сбой — PARTIAL с перечнем созданного, без
    удаления. Итог ZPROBE_B15_INSTALL."""
    lock = REL.install_lock()
    if lock is None:
        print('ZPROBE_B15_INSTALL=REFUSED another install is running; nothing changed')
        return 1
    try:
        zp = common(pkg, rep)
        tg = targets(pkg)
        p = B9.parent_problems(tg)
        rep.add('PARENTS', 'FAIL' if p else 'OK', '; '.join(sorted(set(p))) or '-')
        if rep.fails or zp is None:
            print(f'ZPROBE_B15_INSTALL=REFUSED checks fails={rep.fails}; nothing created')
            return 1
        acts, probs = B9.plan(pkg)
        if probs or not acts:
            for x in probs:
                print('CONFLICT ' + x)
            print('ZPROBE_B15_INSTALL=REFUSED ' + ('conflicts=%d' % len(probs) if probs else 'already installed')
                  + '; nothing created')
            return 1
        done = []
        os.umask(0o077)
        j = REL.Journal(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        try:
            REL.apply(acts, done, j)
            sync_dirs(tg)
        except Exception as x:  # noqa: BLE001
            print(f'ZPROBE_B15_INSTALL=PARTIAL STOP created={done} journal={j.path} error={type(x).__name__}: {x}; '
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
        print('ZPROBE_B15_INSTALL=' + ('OK' if ok else 'REFUSED installed state does not match; STOP, nothing removed'))
        return 0 if ok else 1
    finally:
        os.close(lock)


# Переменные и функции модулей B9 и B10 — на значения B15 (их функции берут их из своего модуля в момент вызова).
B9.LIB, B9.UNITS, B9.LIB_FILES, B9.UNIT_SHOW, B9.WATCH_UNITS = LIB, UNITS, LIB_FILES, UNIT_SHOW, WATCH_UNITS
B9.KNOWN_SERIES, B9.EXPECT_SEGMENTS, B9.EXPECT_SEQ = KNOWN_SERIES, EXPECT_SEGMENTS, EXPECT_SEQ
B9.EXPECT_DIGEST, B9.EXPECT_LAST = EXPECT_DIGEST, EXPECT_LAST
B10.STARTED_SERIES, B10.KNOWN_SERIES = STARTED_SERIES, KNOWN_SERIES
B9.targets, B9.unit_expect, B9.common, B9.verify_installed = targets, unit_expect, common, verify_installed
B9.journal_problems = journal_problems
REL.LIB = LIB
REL.JOURNAL_PREFIX = 'zprobe-install-3.5.5-b15-'
REL.TESTS = '/var/lib/zavod/probes-tests-b15'


def sync_paths():
    """Испытания меняют LIB и UNIT_DIR этого модуля — те же значения нужны модулям B9 и выпуска."""
    B9.LIB, B9.UNIT_DIR, REL.LIB = LIB, UNIT_DIR, LIB


def main():
    a = sys.argv[1:]
    modes = {'preflight': preflight, 'verify-installed': verify_installed}
    ok = os.geteuid() == 0 and ((len(a) == 2 and a[0] in ('preflight', 'verify-installed', 'install')) or
                                (len(a) == 3 and a[0] == 'report' and a[2] in modes))
    if not ok:
        print('usage (root): zprobe_release_b15.py preflight|verify-installed|install <package dir> | '
              'report <package dir> preflight|verify-installed')
        return 2
    pkg = os.path.abspath(a[1])
    rep = REL.Report()
    try:
        if a[0] == 'install':
            return install(pkg, rep)
        modes[a[2] if a[0] == 'report' else a[0]](pkg, rep)
    except Exception as x:  # noqa: BLE001 — всегда явный итог
        print(f'ZPROBE_B15_{a[0].upper()}=FAIL error={type(x).__name__}: {x}')
        return 1
    name = (a[2] if a[0] == 'report' else a[0]).upper().replace('-', '_')
    if a[0] == 'report':   # отчёт только в stdout, файла нет (как B12, REL112 M-01)
        text = ('\n'.join(rep.lines) + '\n').encode('utf-8')
        print(f'REPORT_SHA256={REL.sha_b(text)} lines={len(rep.lines)} '
              '(stdout only, no file written; diagnostics, not a permission)')
    print(f'ZPROBE_B15_{name}={"FAIL" if rep.fails else "OK"} fails={rep.fails}')
    return 1 if rep.fails else 0


if __name__ == '__main__':
    sys.exit(main())
