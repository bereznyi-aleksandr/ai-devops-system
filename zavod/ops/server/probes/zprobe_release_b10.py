#!/usr/bin/python3
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_release_b10.py
# ВЕРСИЯ: v0.1 (выпуск B10)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-15 00:18 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-15 00:18 +02:00
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
import os
import stat
import sys

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

# Якорь журнала и отметка начала — значения B9 (состояние после pb1trial1), не придуманы заново.
# ДО УСТАНОВКИ B10 ЗНАЧЕНИЯ СВЕРИТЬ ЧТЕНИЕМ НА СЕРВЕРЕ: после pb1trial2 журнал и папка started уже другие, поэтому с
# этими значениями preflight B10 ждаемо даст FAIL (JOURNAL, STARTED) — их вносят после чтения на сервере, как в B9 v0.5.
KNOWN_SERIES = B9.KNOWN_SERIES
EXPECT_SEGMENTS, EXPECT_SEQ = B9.EXPECT_SEGMENTS, B9.EXPECT_SEQ
EXPECT_DIGEST = B9.EXPECT_DIGEST
EXPECT_LAST = B9.EXPECT_LAST

_b9_targets = B9.targets
_b9_common = B9.common
_b9_unit_expect = B9.unit_expect
_b9_verify_installed = B9.verify_installed


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
    """Свойства служб B10: те же, что у B9, имена служб — b10 (папка программ уже LIB B10)."""
    def fix(v):
        if isinstance(v, str):
            return v.replace('zprobe-journal-b9@', 'zprobe-journal-b10@').replace('zprobe-run-b9@', 'zprobe-run-b10@')
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
            extra = sorted(set(os.listdir(B9_LIB)) - set(B9_LIB_KEYS) - {'RELEASE'})
            if extra:
                probs.append(f'B9 {B9_LIB} holds other files: {extra[:5]}')
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


def common(pkg, rep):
    """Проверка B9 (новая в B10), затем общий список B9 (B8, службы, учётная запись, журнал, отметки)."""
    p = b9_problems(pkg)
    rep.add('B9', 'FAIL' if p else 'OK', '; '.join(p) or '-')
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
