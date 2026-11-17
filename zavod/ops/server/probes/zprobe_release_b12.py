#!/usr/bin/python3
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_release_b12.py
# ВЕРСИЯ: v0.1 (выпуск B12)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-17 23:50 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-17 23:50 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминальный чат zavod (ad796548)
# НАЗНАЧЕНИЕ: установка B12 (диагностика H4: zprobe_checks.py v0.7, zprobe_r2.py v0.10; код принят REL111 AGREED, сборка
#   разрешена B12_RELEASE_BUILD_ALLOWED=YES) рядом с B8, B9, B10 и B11. Строится на zprobe_release_b11.py: его модуль
#   (и через него B10 и B9) берётся целиком, здесь свои цели и своя проверка «B11 цел». Отличия от B11:
#   - папка программ /usr/local/lib/zavod/probes-b12 — ровно: те же 7 модулей (всё, что импортирует zprobe_r2.py),
#     RELEASE, своя копия отпечатков B9 zprobe_pins_b9.txt и INSTALLED.sha256 (10 файлов);
#   - НОВЫХ СЛУЖБ НЕТ (как B11): /etc/systemd/system не трогается, daemon-reload и systemd-analyze не вызываются;
#   - B8, B9, B10 И B11 целы (только чтение): B8, B9, B10 — проверками B11; B11 — каждый файл папки probes-b11 равен
#     отпечаткам B11 (zavod/ops/zprobe_pins_b11.txt в пакете), обычный файл root:root 0644 с одной ссылкой; RELEASE B11 —
#     коммит выпуска B11 76db3a69c…; INSTALLED.sha256 B11 — байт в байт список, собранный заново из отпечатков B11; в папке
#     B11 нет лишних файлов (в том числе __pycache__); сама папка — обычная папка root:root 0755. B12 ничего в B11 не пишет;
#   - REL111 Q3 «жёстко сверять с известными независимыми отпечатками»: четыре файла отпечатков в пакете (B8, B9, B10, B11)
#     обязаны иметь SHA-256 из PINS_FILE_SHA (суммы файлов замороженного выпуска B11 abb1575f9), а отпечатки B11 —
#     release_commit B11_RELEASE_COMMIT; иначе FAIL PKG_MODULES и ничего не ставится;
#   - модули B12, кроме zprobe_checks.py и zprobe_r2.py, обязаны быть байт в байт равны отпечаткам B11 (иначе выпуск не
#     собирается, а при установке — FAIL PKG_MODULES); копия отпечатков B9 в пакете — равна записи B11 о ней;
#   - дневник тот же (INTENT → CREATED → DONE, O_EXCL, fsync), префикс zprobe-install-3.5.5-b12-, папка испытаний
#     /var/lib/zavod/probes-tests-b12.
#   Режимы те же: preflight | verify-installed | install <пакет> | report <пакет> preflight|verify-installed.
# КАК ЗАПУСКАЕТСЯ R2 ИЗ B12 (команду R2 этот файл не делает; описание для аудита): от root, после установки B12, аудита
#   установки и «да» оператора на НОВУЮ команду R2. Тело — как команда R2 B11, но папка программ
#   L=/usr/local/lib/zavod/probes-b12 (ровно 10 файлов), плюс проверка, что B10 и B11 целы; последняя строка —
#   `exec /usr/bin/python3 -I -B "$L/zprobe_r2.py" pb1trial2`. Код выхода: 0 — SAFE_PRE_START, 1 — BLOCKED_*, 2 — REFUSED_*.
# ДОПУЩЕНИЯ (на аудит): 1) zprobe-start в B12 не ставится (как в B11); 2) копия отпечатков B9 в probes-b12 — своя, её
#   равенство копии B11 видно по INSTALLED.sha256 обоих; 3) папка наблюдений R2 /var/lib/zavod/r2obs и печать
#   /var/lib/zavod/seal установщиком не трогаются и не проверяются (их проверяет сама R2); 4) журнал серий и отметки
#   начала проверяются так же, как у B11.
# ОГРАНИЧЕНИЯ: B8, B9, B10, B11 только читаются; ничего не удаляется, не переименовывается и не перезаписывается. Модуль
#   меняет переменные zprobe_release_b9 (targets) и zprobe_release в своём процессе — не импортировать вместе с установкой
#   B9, B10 или B11 в одном процессе. SQL этот выпуск не ставит.
import datetime
import os
import stat
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zprobe_release_b11 as B11  # noqa: E402

B10 = B11.B10
B9 = B11.B9
REL = B11.REL

# пути — переменные модуля (испытания подменяют их на папку испытания; пути B8–B11 и служб — в B11, B10 и B9)
LIB = '/usr/local/lib/zavod/probes-b12'
MODULES = B11.MODULES
CHANGED = ('zprobe_checks.py', 'zprobe_r2.py')          # единственные модули B12, отличные от B11
LIB_FILES = {n: 0o644 for n in MODULES}
UNITS = ()                                               # новых служб нет
PINS_B9_SRC, PINS_B10_SRC = B11.PINS_B9_SRC, B11.PINS_B10_SRC
PINS_B8_SRC = os.path.join('zavod', 'ops', 'zprobe_pins_b8.txt')
PINS_B11_SRC = os.path.join('zavod', 'ops', 'zprobe_pins_b11.txt')
PINS_B9_NAME, INSTALLED_NAME = B11.PINS_B9_NAME, B11.INSTALLED_NAME
B11_RELEASE_VERSION = '3.5.5-b11'
B11_RELEASE_COMMIT = '76db3a69c7819c370000b58524cf672a10d48057'
# Известные отпечатки файлов отпечатков (SHA-256 файлов коммита выпуска B11 abb1575f98d0b72cdf05b182cf063ba642cb32de).
PINS_FILE_SHA = {
    PINS_B8_SRC: 'ef5c9962fd5aa15ce11a1832529693bbcbecc85353ed2687b426e5088bc61fe1',
    PINS_B9_SRC: '91ed266ae21a3719463a4b49d20c5d9f5ed797cd6dbbdaf9dbbaa60d4fbaa712',
    PINS_B10_SRC: 'a86ea709d6de2c789a39efeb047a6fc5f25365a200dc3df39e0d3924aed883db',
    PINS_B11_SRC: 'f0a989d642ce1f459ad64b205743b82a8012ace6eac905082ef75b9d759c1089'}
# Ключи отпечатков B11 (zavod/ops/zprobe_pins_b11.txt) — строгий разбор: ровно эти и release_commit.
B11_PIN_KEYS = tuple(B11.LIB_FILES) + (B11.PINS_B9_NAME,)


def installed_path():
    return os.path.join(LIB, INSTALLED_NAME)


def read(path):
    with open(path, 'rb') as f:
        return f.read()


def pins11(pkg):
    """Отпечатки B11 из пакета: строгий разбор и коммит выпуска B11 (иначе REL.Refused)."""
    pins = B9.read_pins_file(os.path.join(pkg, PINS_B11_SRC), B11_PIN_KEYS)
    if pins['release_commit'] != B11_RELEASE_COMMIT:
        raise REL.Refused(f'zprobe_pins_b11.txt: release_commit {pins["release_commit"]} is not B11 {B11_RELEASE_COMMIT}')
    return pins


def targets(pkg):
    """Цели B12: (путь, байты, права); первой — папка LIB; затем модули, RELEASE, копия отпечатков B9 и последней —
    INSTALLED.sha256 со списком всех предыдущих файлов (формат B10/B11: «<sha256>  <путь>», по пути)."""
    src = os.path.join(pkg, 'zavod', 'ops', 'server', 'probes')
    out = [(LIB, None, 0o755)]
    for n, mode in LIB_FILES.items():
        out.append((os.path.join(LIB, n), read(os.path.join(src, n)), mode))
    out.append((os.path.join(LIB, 'RELEASE'), read(os.path.join(pkg, 'RELEASE')), 0o644))
    out.append((os.path.join(LIB, PINS_B9_NAME), read(os.path.join(pkg, PINS_B9_SRC)), 0o644))
    out.append((installed_path(), B10.installed_bytes(out), 0o644))
    return out


def pkg_problems(pkg):
    """Состав пакета: четыре файла отпечатков — известные суммы; отпечатки B11 — коммит B11; модули B12, кроме CHANGED,
    равны отпечаткам B11; копия отпечатков B9 в пакете равна записи B11 о ней."""
    probs = []
    for rel, want in sorted(PINS_FILE_SHA.items()):
        try:
            got = REL.sha_b(read(os.path.join(pkg, rel)))
        except OSError as x:
            probs.append(f'package {rel} {type(x).__name__}')
            continue
        if got != want:
            probs.append(f'package {rel} differs from the known B11-release sum')
    if probs:
        return probs
    try:
        pins = pins11(pkg)
    except (OSError, REL.Refused, ValueError) as x:
        return [f'package B11 pins: {type(x).__name__}: {x}']
    src = os.path.join(pkg, 'zavod', 'ops', 'server', 'probes')
    for n in MODULES:
        if n in CHANGED:
            continue
        try:
            got = REL.sha_b(read(os.path.join(src, n)))
        except OSError as x:
            probs.append(f'package {n} {type(x).__name__}')
            continue
        if got != pins[n]:
            probs.append(f'package {n} differs from B11 pins')
    if REL.sha_b(read(os.path.join(pkg, PINS_B9_SRC))) != pins[PINS_B9_NAME]:
        probs.append(f'package {PINS_B9_SRC} differs from the B11 record of it')
    return probs


def b11_installed_expected(pins):
    """INSTALLED.sha256 B11, собранный заново из отпечатков B11: 7 модулей, RELEASE и копия отпечатков B9 — строка
    «<sha256>  <путь>» на каждый, по пути (как B10.installed_bytes)."""
    lib = B11.LIB
    rel = f'commit={pins["release_commit"]}\nversion={B11_RELEASE_VERSION}\n'.encode('ascii')
    rows = [(os.path.join(lib, n), pins[n]) for n in B11.LIB_FILES]
    rows.append((os.path.join(lib, 'RELEASE'), REL.sha_b(rel)))
    rows.append((os.path.join(lib, PINS_B9_NAME), pins[PINS_B9_NAME]))
    return ''.join(f'{h}  {p}\n' for p, h in sorted(rows)).encode('ascii'), rel


def b11_problems(pkg):
    """B11 цел (только чтение): файлы папки B11 — те же SHA-256, что в отпечатках B11 (обычный файл, root:root, 0644,
    одна ссылка); RELEASE B11 — коммит выпуска B11; INSTALLED.sha256 B11 — байт в байт список, собранный заново из
    отпечатков; папка — обычная, root:root 0755; лишних файлов (в том числе __pycache__) нет."""
    try:
        pins = pins11(pkg)
        want_list, want_rel = b11_installed_expected(pins)
    except (OSError, REL.Refused, ValueError) as x:
        return [f'B11 pins in the package: {type(x).__name__}: {x}']
    probs = []
    lib = B11.LIB
    files = {os.path.join(lib, k): (pins[k], B11.LIB_FILES[k]) for k in B11.LIB_FILES}
    files[os.path.join(lib, 'RELEASE')] = (REL.sha_b(want_rel), 0o644)
    files[os.path.join(lib, PINS_B9_NAME)] = (pins[PINS_B9_NAME], 0o644)
    files[os.path.join(lib, INSTALLED_NAME)] = (REL.sha_b(want_list), 0o644)
    try:
        st = os.lstat(lib)
        if not stat.S_ISDIR(st.st_mode):
            return [f'B11 {lib} is not a plain folder']
        if (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) != (REL.ROOT_UID, REL.ROOT_GID, 0o755):
            probs.append(f'B11 {lib} owner or mode differs from the B11 release')
        extra = sorted(set(os.listdir(lib)) - {os.path.basename(p) for p in files})
        if extra:
            probs.append(f'B11 {lib} holds other files: {extra[:5]}')
    except OSError as x:
        return [f'B11 {lib} {type(x).__name__}']
    for p, (h, mode) in sorted(files.items()):
        try:
            st = os.lstat(p)
        except OSError as x:
            probs.append(f'B11 {p} {type(x).__name__}')
            continue
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            probs.append(f'B11 {p} is not a plain single-link file')
        elif (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) != (REL.ROOT_UID, REL.ROOT_GID, mode):
            probs.append(f'B11 {p} owner or mode differs from the B11 release')
        elif REL.sha(p) != h:
            probs.append(f'B11 {p} differs from B11 pins')
    return probs


def common(pkg, rep):
    """Общий список B12: состав пакета, B8, B9 (с допуском байт-кода как в B10/B11), B10, B11, службы (ничего не
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
    p = b11_problems(pkg)
    rep.add('B11', 'FAIL' if p else 'OK', '; '.join(p) or '-')
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


def lib_extra_problems(tg):
    """В папке программ B12 ровно файлы целей — ни __pycache__, ни иного."""
    own = {os.path.basename(p) for p, _, _ in tg if os.path.dirname(p) == LIB}
    try:
        extra = sorted(set(os.listdir(LIB)) - own)
    except OSError as x:
        return [f'{LIB} {type(x).__name__}']
    return [f'{LIB} holds other files: {extra[:5]}'] if extra else []


def installed_problems(pkg):
    """INSTALLED.sha256 B12 = ожидаемый список (root, 0644, байт в байт); каждый файл списка сейчас с той же суммой;
    в папке B12 нет лишнего."""
    tg = targets(pkg)
    path, data, mode = tg[-1]
    s = B9.target_state(path, data, mode)
    if s != 'same':
        return [f'{path}: {s}']
    probs = []
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
    """Как install B11: проверки, план B9-порядка, дневник, создание только новых целей B12, fsync папок,
    verify-installed. Итог ZPROBE_B12_INSTALL."""
    lock = REL.install_lock()
    if lock is None:
        print('ZPROBE_B12_INSTALL=REFUSED another install is running; nothing changed')
        return 1
    try:
        zp = common(pkg, rep)
        tg = targets(pkg)
        p = B9.parent_problems(tg)
        rep.add('PARENTS', 'FAIL' if p else 'OK', '; '.join(sorted(set(p))) or '-')
        if rep.fails or zp is None:
            print(f'ZPROBE_B12_INSTALL=REFUSED checks fails={rep.fails}; nothing created')
            return 1
        acts, probs = B9.plan(pkg)
        if probs or not acts:
            for x in probs:
                print('CONFLICT ' + x)
            print('ZPROBE_B12_INSTALL=REFUSED ' + ('conflicts=%d' % len(probs) if probs else 'already installed')
                  + '; nothing created')
            return 1
        done = []
        os.umask(0o077)
        j = REL.Journal(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        try:
            REL.apply(acts, done, j)
            sync_dirs(tg)
        except Exception as x:  # noqa: BLE001
            print(f'ZPROBE_B12_INSTALL=PARTIAL created={done} journal={j.path} error={type(x).__name__}: {x}; '
                  'nothing removed; run install again: it finishes only objects of this release from the journal')
            return 1
        finally:
            j.close()
        print(f'INSTALLED_NEW={done} journal={j.path} (no services: no daemon-reload, no systemd-analyze)')
        rep2 = REL.Report()
        verify_installed(pkg, rep2)
        ok = not rep2.fails
        print('ZPROBE_B12_INSTALL=' + ('OK' if ok else 'REFUSED installed state does not match; nothing removed'))
        return 0 if ok else 1
    finally:
        os.close(lock)


# Функции B9 (план и общий проход создания) берут цели из своего модуля в момент вызова — на цели B12.
B9.targets = targets
REL.JOURNAL_PREFIX = 'zprobe-install-3.5.5-b12-'
REL.TESTS = '/var/lib/zavod/probes-tests-b12'
REL.LIB = LIB


def main():
    a = sys.argv[1:]
    modes = {'preflight': preflight, 'verify-installed': verify_installed}
    ok = os.geteuid() == 0 and ((len(a) == 2 and a[0] in ('preflight', 'verify-installed', 'install')) or
                                (len(a) == 3 and a[0] == 'report' and a[2] in modes))
    if not ok:
        print('usage (root): zprobe_release_b12.py preflight|verify-installed|install <package dir> | '
              'report <package dir> preflight|verify-installed')
        return 2
    pkg = os.path.abspath(a[1])
    rep = REL.Report()
    try:
        if a[0] == 'install':
            return install(pkg, rep)
        modes[a[2] if a[0] == 'report' else a[0]](pkg, rep)
    except Exception as x:  # noqa: BLE001 — всегда явный итог
        print(f'ZPROBE_B12_{a[0].upper()}=FAIL error={type(x).__name__}: {x}')
        return 1
    name = (a[2] if a[0] == 'report' else a[0]).upper().replace('-', '_')
    if a[0] == 'report':
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        path = REL.new_file(os.path.join(REL.JOURNAL_DIR, REL.JOURNAL_PREFIX + '{}.report'), stamp,
                            ('\n'.join(rep.lines) + '\n').encode('utf-8'))
        print(f'REPORT={path} SHA256={REL.sha(path)} (diagnostics, not a permission)')
    print(f'ZPROBE_B12_{name}={"FAIL" if rep.fails else "OK"} fails={rep.fails}')
    return 1 if rep.fails else 0


if __name__ == '__main__':
    sys.exit(main())
