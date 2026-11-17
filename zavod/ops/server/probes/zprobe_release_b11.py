#!/usr/bin/python3
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_release_b11.py
# ВЕРСИЯ: v0.1 (выпуск B11)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-17 07:04 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-17 07:04 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминальный чат zavod (ee9861cd)
# НАЗНАЧЕНИЕ: установка B11 рядом с B8, B9 и B10 (решение аудита REL96B PATH=A: B11 только для шага R2 — печать остатка
#   pb1trial2 с новой zprobe_checks.py v0.4). Строится на zprobe_release_b10.py: его модуль (и через него B9) берётся
#   целиком, здесь свои цели и своя проверка «B10 цел». Отличия от B10:
#   - папка программ /usr/local/lib/zavod/probes-b11 — ровно: zprobe_r2.py, zprobe_checks.py, zprobe_export_rules.py,
#     zprobe_rules.py, zprobe_seal.py, zprobe_unstarted.py, zprobe_dropin.py (всё, что импортирует zprobe_r2.py),
#     RELEASE, копия отпечатков B9 zprobe_pins_b9.txt (эталон службы B9 для R2) и INSTALLED.sha256;
#   - НОВЫХ СЛУЖБ НЕТ: файлов в /etc/systemd/system не создаётся, daemon-reload и systemd-analyze не вызываются;
#   - B8, B9 И B10 целы: B8 и B9 — как в B10 (отпечатки B8 и B9 из пакета); B10 — каждый файл папки probes-b10 и служб
#     *-b10@ равен отпечаткам B10 (zavod/ops/zprobe_pins_b10.txt в пакете, права root, одна ссылка), RELEASE B10 — коммит
#     выпуска B10, список INSTALLED.sha256 B10 равен списку, собранному заново из отпечатков (байт в байт), лишних файлов
#     в папке B10 нет; B11 ничего в B10 не пишет;
#   - модули B11, кроме zprobe_checks.py и zprobe_r2.py, обязаны быть байт в байт равны отпечаткам B10 (иначе выпуск
#     не собирается, а при установке — FAIL PKG_MODULES);
#   - дневник тот же (INTENT → CREATED → DONE, O_EXCL, fsync), префикс zprobe-install-3.5.5-b11-, папка испытаний
#     /var/lib/zavod/probes-tests-b11.
#   Режимы те же: preflight | verify-installed | install <пакет> | report <пакет> preflight|verify-installed.
# КАК ЗАПУСКАЕТСЯ R2 ИЗ B11 (команду R2 этот файл не делает; описание для аудита): от root, после установки B11 и
#   «да» оператора на НОВУЮ команду R2 — прежнее «да R2 v4» на неё не распространяется. Тело команды — как r2_precheck.sh
#   v0.4, но папка программ L=/usr/local/lib/zavod/probes-b11 (ровно 10 файлов: 7 модулей, RELEASE, zprobe_pins_b9.txt,
#   INSTALLED.sha256), плюс проверка, что B10 цел; пустая папка /var/lib/zavod/seal root:root 0700 принимается как есть
#   (R2_SEALROOT=OK); последняя строка — не zprobe-start (его в B11 нет, а он зашит на probes-b10), а ровно то, что
#   делает его ветка --seal-residue: `exec /usr/bin/python3 -I -B "$L/zprobe_r2.py" pb1trial2` (root; -I -B —
#   байт-код в папку B11 не пишется). Код выхода: 0 — SAFE_PRE_START, 1 — BLOCKED_*, 2 — REFUSED_*.
# ДОПУЩЕНИЯ (на аудит): 1) zprobe-start в B11 не ставится — ветка --seal-residue состоит из одного exec (проверено
#   тестом N23 B10), служб и журнала серий B11 не нужны; 2) копия отпечатков B9 в probes-b11 — своя (не ссылка на B10):
#   папка B11 самодостаточна, а равенство её файлу B10 проверяет этот установщик (INSTALLED B10 содержит её сумму);
#   3) эталон шаблона службы b10 (zprobe_unstarted.TEMPLATE и строка INSTALLED.sha256 B10) в пути R2 не используется:
#   R2 берёт эталон B9 из zprobe_pins_b9.txt — поэтому INSTALLED.sha256 B11 без строки шаблона; 4) журнал серий B9/B10 и
#   отметки начала проверяются так же, как у B10 (B11 их не меняет).
# ОГРАНИЧЕНИЯ: B8, B9, B10 только читаются; ничего не удаляется, не переименовывается и не перезаписывается. Модуль меняет
#   переменные zprobe_release_b9 (targets) и zprobe_release в своём процессе — не импортировать вместе с установкой B9
#   или B10 в одном процессе. SQL этот выпуск не ставит.
import datetime
import os
import stat
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zprobe_release_b10 as B10  # noqa: E402

B9 = B10.B9
REL = B10.REL

# пути — переменные модуля (испытания подменяют их на папку испытания; пути B8, B9, B10 и служб — в B10 и B9)
LIB = '/usr/local/lib/zavod/probes-b11'
MODULES = ('zprobe_r2.py', 'zprobe_checks.py', 'zprobe_export_rules.py', 'zprobe_rules.py', 'zprobe_seal.py',
           'zprobe_unstarted.py', 'zprobe_dropin.py')
CHANGED = ('zprobe_checks.py', 'zprobe_r2.py')          # единственные модули B11, отличные от B10
LIB_FILES = {n: 0o644 for n in MODULES}
UNITS = ()                                               # новых служб нет
PINS_B9_SRC, PINS_B10_SRC = B10.PINS_B9_SRC, os.path.join('zavod', 'ops', 'zprobe_pins_b10.txt')
PINS_B9_NAME, INSTALLED_NAME = B10.PINS_B9_NAME, B10.INSTALLED_NAME
B10_RELEASE_VERSION = '3.5.5-b10'
# Ключи отпечатков B10 (zavod/ops/zprobe_pins_b10.txt) — строгий разбор: ровно эти и release_commit.
B10_PIN_KEYS = tuple(B10.LIB_FILES) + tuple(B10.UNITS) + tuple(B9.B8_CELL) + (
    'phone_zprobe_verify.py', 'phone_zprobe_rules.py', 'pc_zprobe_refs.sh', 'pc_zprobe_refs_check.py',
    'pc_zprobe_rules.py', 'pc_zprobe_verify_export.py', 'pc_zprobe_export_rules.py', 'pc_zprobe_seal.py')


def installed_path():
    return os.path.join(LIB, INSTALLED_NAME)


def read(path):
    with open(path, 'rb') as f:
        return f.read()


def pins10(pkg):
    return B9.read_pins_file(os.path.join(pkg, PINS_B10_SRC), B10_PIN_KEYS)


def targets(pkg):
    """Цели B11: (путь, байты, права); первой — папка LIB; затем модули, RELEASE, копия отпечатков B9 и последней —
    INSTALLED.sha256 со списком всех предыдущих файлов (формат B10: «<sha256>  <путь>», по пути)."""
    src = os.path.join(pkg, 'zavod', 'ops', 'server', 'probes')
    out = [(LIB, None, 0o755)]
    for n, mode in LIB_FILES.items():
        out.append((os.path.join(LIB, n), read(os.path.join(src, n)), mode))
    out.append((os.path.join(LIB, 'RELEASE'), read(os.path.join(pkg, 'RELEASE')), 0o644))
    out.append((os.path.join(LIB, PINS_B9_NAME), read(os.path.join(pkg, PINS_B9_SRC)), 0o644))
    out.append((installed_path(), B10.installed_bytes(out), 0o644))
    return out


def pkg_problems(pkg):
    """Состав пакета: модули B11, кроме CHANGED, равны отпечаткам B10; копия отпечатков B9 равна ожидаемой B10."""
    probs = []
    src = os.path.join(pkg, 'zavod', 'ops', 'server', 'probes')
    try:
        pins = pins10(pkg)
    except (OSError, REL.Refused, ValueError) as x:
        return [f'package B10 pins: {type(x).__name__}: {x}']
    for n in MODULES:
        if n in CHANGED:
            continue
        try:
            got = REL.sha_b(read(os.path.join(src, n)))
        except OSError as x:
            probs.append(f'package {n} {type(x).__name__}')
            continue
        if got != pins[n]:
            probs.append(f'package {n} differs from B10 pins')
    return probs


def b10_installed_expected(pkg, pins):
    """INSTALLED.sha256 B10, собранный заново из отпечатков B10: 13 файлов программ, RELEASE, копия отпечатков B9 и две
    службы — строка «<sha256>  <путь>» на каждый, по пути (как B10.installed_bytes)."""
    b10lib = B10.LIB
    rel = f'commit={pins["release_commit"]}\nversion={B10_RELEASE_VERSION}\n'.encode('ascii')
    rows = [(os.path.join(b10lib, n), pins[n]) for n in B10.LIB_FILES]
    rows.append((os.path.join(b10lib, 'RELEASE'), REL.sha_b(rel)))
    rows.append((os.path.join(b10lib, PINS_B9_NAME), REL.sha_b(read(os.path.join(pkg, PINS_B9_SRC)))))
    rows += [(os.path.join(B10.UNIT_DIR, u), pins[u]) for u in B10.UNITS]
    return ''.join(f'{h}  {p}\n' for p, h in sorted(rows)).encode('ascii'), rel


def b10_problems(pkg):
    """B10 цел (только чтение): файлы папки B10 и служб *-b10@ — те же SHA-256, что в отпечатках B10 (обычный файл,
    root:root, нужные права, одна ссылка); RELEASE B10 — коммит выпуска B10; INSTALLED.sha256 B10 — байт в байт список,
    собранный заново из отпечатков; в папке B10 нет лишних файлов (в том числе __pycache__)."""
    try:
        pins = pins10(pkg)
        want_list, want_rel = b10_installed_expected(pkg, pins)
    except (OSError, REL.Refused, ValueError) as x:
        return [f'B10 pins in the package: {type(x).__name__}: {x}']
    probs = []
    files = {os.path.join(B10.LIB, k): (pins[k], B10.LIB_FILES[k]) for k in B10.LIB_FILES}
    files.update({os.path.join(B10.UNIT_DIR, u): (pins[u], 0o644) for u in B10.UNITS})
    files[os.path.join(B10.LIB, 'RELEASE')] = (REL.sha_b(want_rel), 0o644)
    files[os.path.join(B10.LIB, PINS_B9_NAME)] = (REL.sha_b(read(os.path.join(pkg, PINS_B9_SRC))), 0o644)
    files[os.path.join(B10.LIB, INSTALLED_NAME)] = (REL.sha_b(want_list), 0o644)
    for p, (h, mode) in sorted(files.items()):
        try:
            st = os.lstat(p)
        except OSError as x:
            probs.append(f'B10 {p} {type(x).__name__}')
            continue
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            probs.append(f'B10 {p} is not a plain single-link file')
        elif (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) != (REL.ROOT_UID, REL.ROOT_GID, mode):
            probs.append(f'B10 {p} owner or mode differs from the B10 release')
        elif REL.sha(p) != h:
            probs.append(f'B10 {p} differs from B10 pins')
    try:
        if os.path.islink(B10.LIB) or not os.path.isdir(B10.LIB):
            probs.append(f'B10 {B10.LIB} is not a plain folder')
        else:
            extra = sorted(set(os.listdir(B10.LIB)) - {os.path.basename(p) for p in files
                                                       if os.path.dirname(p) == B10.LIB})
            if extra:
                probs.append(f'B10 {B10.LIB} holds other files: {extra[:5]}')
    except OSError as x:
        probs.append(f'B10 {B10.LIB} {type(x).__name__}')
    return probs


def common(pkg, rep):
    """Общий список B11: состав пакета, B8, B9 (с допуском байт-кода как в B10), B10, службы (ничего не работает),
    учётная запись, журнал и отметки серий (как у B10). Возвращает учётную запись zprobe или None."""
    p = pkg_problems(pkg)
    rep.add('PKG_MODULES', 'FAIL' if p else 'OK', '; '.join(p) or '-')
    p = B9.b8_problems(pkg)
    rep.add('B8', 'FAIL' if p else 'OK', '; '.join(p) or '-')
    p = B10.b9_problems(pkg)
    pyc = [] if p else B10.pycache_problems()[1]
    rep.add('B9', 'FAIL' if p else 'OK', '; '.join(p) or (
        f'- (B9 bytecode folder {B10.B9_PYCACHE}: {len(pyc)} .pyc of B9 modules, tolerated)' if pyc else '-'))
    p = b10_problems(pkg)
    rep.add('B10', 'FAIL' if p else 'OK', '; '.join(p) or '-')
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
    """В папке программ B11 ровно файлы целей — ни __pycache__, ни иного."""
    own = {os.path.basename(p) for p, _, _ in tg if os.path.dirname(p) == LIB}
    try:
        extra = sorted(set(os.listdir(LIB)) - own)
    except OSError as x:
        return [f'{LIB} {type(x).__name__}']
    return [f'{LIB} holds other files: {extra[:5]}'] if extra else []


def installed_problems(pkg):
    """INSTALLED.sha256 B11 = ожидаемый список (root, 0644, байт в байт); каждый файл списка сейчас с той же суммой;
    в папке B11 нет лишнего."""
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
    """Как install B10 без служб: проверки, план B9-порядка, дневник, создание только новых целей B11, fsync папок,
    verify-installed. Итог ZPROBE_B11_INSTALL."""
    lock = REL.install_lock()
    if lock is None:
        print('ZPROBE_B11_INSTALL=REFUSED another install is running; nothing changed')
        return 1
    try:
        zp = common(pkg, rep)
        tg = targets(pkg)
        p = B9.parent_problems(tg)
        rep.add('PARENTS', 'FAIL' if p else 'OK', '; '.join(sorted(set(p))) or '-')
        if rep.fails or zp is None:
            print(f'ZPROBE_B11_INSTALL=REFUSED checks fails={rep.fails}; nothing created')
            return 1
        acts, probs = B9.plan(pkg)
        if probs or not acts:
            for x in probs:
                print('CONFLICT ' + x)
            print('ZPROBE_B11_INSTALL=REFUSED ' + ('conflicts=%d' % len(probs) if probs else 'already installed')
                  + '; nothing created')
            return 1
        done = []
        os.umask(0o077)
        j = REL.Journal(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        try:
            REL.apply(acts, done, j)
            sync_dirs(tg)
        except Exception as x:  # noqa: BLE001
            print(f'ZPROBE_B11_INSTALL=PARTIAL created={done} journal={j.path} error={type(x).__name__}: {x}; '
                  'nothing removed; run install again: it finishes only objects of this release from the journal')
            return 1
        finally:
            j.close()
        print(f'INSTALLED_NEW={done} journal={j.path} (no services: no daemon-reload, no systemd-analyze)')
        rep2 = REL.Report()
        verify_installed(pkg, rep2)
        ok = not rep2.fails
        print('ZPROBE_B11_INSTALL=' + ('OK' if ok else 'REFUSED installed state does not match; nothing removed'))
        return 0 if ok else 1
    finally:
        os.close(lock)


# Функции B9 (план и общий проход создания) берут цели из своего модуля в момент вызова — на цели B11.
B9.targets = targets
REL.JOURNAL_PREFIX = 'zprobe-install-3.5.5-b11-'
REL.TESTS = '/var/lib/zavod/probes-tests-b11'
REL.LIB = LIB


def main():
    a = sys.argv[1:]
    modes = {'preflight': preflight, 'verify-installed': verify_installed}
    ok = os.geteuid() == 0 and ((len(a) == 2 and a[0] in ('preflight', 'verify-installed', 'install')) or
                                (len(a) == 3 and a[0] == 'report' and a[2] in modes))
    if not ok:
        print('usage (root): zprobe_release_b11.py preflight|verify-installed|install <package dir> | '
              'report <package dir> preflight|verify-installed')
        return 2
    pkg = os.path.abspath(a[1])
    rep = REL.Report()
    try:
        if a[0] == 'install':
            return install(pkg, rep)
        modes[a[2] if a[0] == 'report' else a[0]](pkg, rep)
    except Exception as x:  # noqa: BLE001 — всегда явный итог
        print(f'ZPROBE_B11_{a[0].upper()}=FAIL error={type(x).__name__}: {x}')
        return 1
    name = (a[2] if a[0] == 'report' else a[0]).upper().replace('-', '_')
    if a[0] == 'report':
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        path = REL.new_file(os.path.join(REL.JOURNAL_DIR, REL.JOURNAL_PREFIX + '{}.report'), stamp,
                            ('\n'.join(rep.lines) + '\n').encode('utf-8'))
        print(f'REPORT={path} SHA256={REL.sha(path)} (diagnostics, not a permission)')
    print(f'ZPROBE_B11_{name}={"FAIL" if rep.fails else "OK"} fails={rep.fails}')
    return 1 if rep.fails else 0


if __name__ == '__main__':
    sys.exit(main())
