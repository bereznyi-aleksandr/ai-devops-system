#!/usr/bin/python3
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_release_b9.py
# ВЕРСИЯ: v0.3  СТАТУС: DRAFT
# v0.3 (2026-11-14 12:01 +02:00, аудит ChatGPT REL32): M-02 — install принимает уже существующую цель с байтами
#   выпуска только как свою: последняя попытка дневника B9 по пути — INTENT, CREATED (и, может быть, DONE) с тем же
#   видом, суммой, размером, правами и тем же inode (dev, ino); иначе CONFLICT, ничего не создаётся. M-04 —
#   verify-installed сверяет действующие свойства служб: нет drop-in (DropInPaths пусто), NeedDaemonReload=no,
#   команды ExecStart и ExecStopPost по порядку (путь, argv, флаги), IPAddressDeny = any, PrivateIPC,
#   TemporaryFileSystem, BindReadOnlyPaths и остальные ограничения файла службы.
# ДАТА СОЗДАНИЯ: 2026-11-14 10:51 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-14 12:01 +02:00
# v0.2 (CI run 43579303026): предки целей проверяются только вне целей — папку LIB создаёт сама установка, поэтому
#   у файлов внутри LIB проверяются предки LIB (до установки папки нет; прежде это давало PARENTS FAIL всегда).
# ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · 05» (c241e855)
# НАЗНАЧЕНИЕ: установка B9 рядом с B8 (проект DESIGN_B9_3_5_5_20261114_v0_9.md §4 и по его §0: v0.2 §2, §5;
#   v0.4 §4; v0.5 §3). Запускает только администратор (root) командой оператора. Режимы:
#   preflight <пакет>                 — только чтение: ни одной цели B9 нет; B8 цел по отпечаткам B8; журнал,
#                                       отметки, службы, учётная запись; код 0 только тогда;
#   verify-installed <пакет>          — только чтение: все цели B9 есть и равны выпуску; службы B9 загружены из
#                                       своих файлов; B8 цел; журнал годен;
#   report <пакет> preflight|verify-installed — тот же разбор, отчёт новым файлом (O_EXCL), не разрешение;
#   install <пакет>                   — под замком: те же проверки, затем создание только новых целей B9 с дневником
#                                       INTENT → CREATED → DONE (функции zprobe_release.py B8), daemon-reload,
#                                       systemd-analyze verify, verify-installed.
# ОГРАНИЧЕНИЯ: B8 только читается; ничего не удаляется, не переименовывается и не перезаписывается; учётная запись
#   zprobe и папка данных B8 не создаются (их нет — REFUSED); клетка 3.5.2 не ставится. Полные значения якоря журнала
#   (EXPECT_DIGEST, EXPECT_LAST) вносятся после чтения на сервере (план v0.5); пока они неполные — preflight FAIL.
import datetime
import os
import re
import stat
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zprobe_release as REL  # noqa: E402
import zprobe_rules as R  # noqa: E402
import zprobe_journal as J  # noqa: E402

# пути — переменные модуля (испытания подменяют их на папку испытания)
LIB = '/usr/local/lib/zavod/probes-b9'
B8_LIB = '/usr/local/lib/zavod/probes'
UNIT_DIR = '/etc/systemd/system'
DATA = '/var/lib/zavod/probes'
RUN = '/run/zprobe'
MOUNTINFO = '/proc/self/mountinfo'
UNITS = ('zprobe-run-b9@.service', 'zprobe-journal-b9@.service')
LIB_FILES = {'pb1_session.py': 0o644, 'zprobe_rules.py': 0o644, 'zprobe_runner.py': 0o644,
             'zprobe_journal.py': 0o644, 'zprobe-start': 0o755}
B8_LIB_KEYS = ('pb1_session.py', 'zprobe_rules.py', 'zprobe_runner.py', 'zprobe_journal.py', 'zprobe-start')
B8_CELL = {'zagent@.service': '/etc/systemd/system/zagent@.service', 'zavod-proxy': '/usr/local/lib/zavod/zavod-proxy',
           'zavod-gate': '/usr/local/lib/zavod/zavod-gate', 'zavod-egress.nft': '/etc/zavod/zavod-egress.nft'}
UNIT_SHOW = ('zprobe-journal-b9@check.service', 'zprobe-run-b9@check.service')


def any_ip(v):
    """IPAddressDeny=any: systemd показывает его как все адреса IPv4 и IPv6."""
    return set(v.split()) in ({'any'}, {'0.0.0.0/0', '::/0'})


def unit_expect():
    """M-355-REL32-04: действующие свойства служб B9 (systemctl show), как задаёт их файл выпуска без drop-in."""
    py = '/usr/bin/python3'
    common = {'DropInPaths': '', 'NeedDaemonReload': 'no', 'User': 'zprobe', 'Group': 'zprobe', 'UMask': '0077',
              'NoNewPrivileges': 'yes', 'CapabilityBoundingSet': '', 'ProtectSystem': 'strict', 'ProtectHome': 'yes',
              'PrivateTmp': 'yes', 'RestrictAddressFamilies': 'AF_UNIX', 'ReadWritePaths': DATA}
    return {
        UNIT_SHOW[0]: dict(common, FragmentPath=UNIT_DIR + '/zprobe-journal-b9@.service',
                           ExecStartEx=[(py, f'{py} -I {LIB}/zprobe_journal.py commit check', '')], ExecStopPostEx=[],
                           PrivateDevices='yes', PrivateNetwork='yes', PrivateIPC='yes', IPAddressDeny=any_ip,
                           TemporaryFileSystem='/run:ro', BindReadOnlyPaths='/run/zprobe:/run/zprobe:rbind',
                           ProtectKernelTunables='yes', ProtectKernelModules='yes', ProtectControlGroups='yes',
                           LockPersonality='yes'),
        UNIT_SHOW[1]: dict(common, FragmentPath=UNIT_DIR + '/zprobe-run-b9@.service',
                           ExecStartEx=[(py, f'{py} -I {LIB}/zprobe_runner.py run check', 'privileged')],
                           ExecStopPostEx=[(py, f'{py} -I {LIB}/zprobe_runner.py cleanup check',
                                            'ignore-failure privileged'),
                                           ('/usr/bin/systemctl',
                                            '/usr/bin/systemctl start --no-block zprobe-journal-b9@check.service',
                                            'privileged')],
                           ReadOnlyPaths='/run/zprobe')}


def exec_cmds(v):
    """Значение ExecStartEx/ExecStopPostEx → [(путь, argv, флаги)] по порядку."""
    out = []
    for body in re.findall(r'\{ (.*?) \}', v):
        f = dict(x.split('=', 1) for x in body.split(' ; ') if '=' in x)
        out.append((f.get('path'), f.get('argv[]'), f.get('flags', '')))
    return out
WATCH_UNITS = ('zprobe-run@*', 'zprobe-run-b9@*', 'zprobe-journal-b9@*', 'zagent@*')
KNOWN_SERIES = 'pb1trial1'
EXPECT_SEGMENTS, EXPECT_SEQ = 1, 2
EXPECT_DIGEST = '7e46e537'      # R.segments_digest после pb1trial1 (телефон, anchors.log) — пока первые 8 знаков
EXPECT_LAST = '800caf5e'        # SHA-256 последней строки журнала после pb1trial1 — пока первые 8 знаков
REL.LIB = LIB
REL.JOURNAL_PREFIX = 'zprobe-install-3.5.5-b9-'
REL.TESTS = '/var/lib/zavod/probes-tests-b9'


def sh(*a):
    return REL.sh(*a)


def read_pins_file(path, keys):
    """Строгий разбор «ключ значение»: ровно ключи keys и release_commit, без повторов."""
    with open(path, 'rb') as f:
        text = f.read().decode('utf-8')
    pins = {}
    for ln in text.split('\n'):
        if ln == '' or ln.startswith('#'):
            continue
        k, v = ln.split(' ')
        if k in pins or not re.fullmatch(r'[0-9a-f]{40}' if k == 'release_commit' else r'[0-9a-f]{64}', v):
            raise REL.Refused(f'{os.path.basename(path)}: bad or repeated key {k}')
        pins[k] = v
    if set(pins) != set(keys) | {'release_commit'}:
        raise REL.Refused(f'{os.path.basename(path)}: keys differ')
    return pins


def targets(pkg):
    """Цели B9: (путь, байты, права); первой — папка LIB (байты None)."""
    src = os.path.join(pkg, 'zavod', 'ops', 'server', 'probes')
    out = [(LIB, None, 0o755)]
    for n, mode in LIB_FILES.items():
        with open(os.path.join(src, n), 'rb') as f:
            out.append((os.path.join(LIB, n), f.read(), mode))
    with open(os.path.join(pkg, 'RELEASE'), 'rb') as f:
        out.append((os.path.join(LIB, 'RELEASE'), f.read(), 0o644))
    for u in UNITS:
        with open(os.path.join(src, u), 'rb') as f:
            out.append((os.path.join(UNIT_DIR, u), f.read(), 0o644))
    return out


def mounts(text):
    """Точки монтирования из mountinfo (поле 5; \\040 — пробел)."""
    out = set()
    for ln in text.split('\n'):
        f = ln.split(' ')
        if len(f) > 4:
            out.add(f[4].replace('\\040', ' '))
    return out


def mount_problems(paths):
    with open(MOUNTINFO, encoding='utf-8') as f:
        mp = mounts(f.read())
    bad = set()
    for p in paths:
        cur = os.path.abspath(p)
        while cur != os.path.dirname(cur):
            if cur in mp:
                bad.add(cur)
            cur = os.path.dirname(cur)
    return [f'{m} is a mount point on a B9 target path' for m in sorted(bad)]


def b8_problems(pkg):
    """B8 цел: каждый установленный файл B8 и клетки — тот же SHA-256, что в отпечатках B8 (только чтение)."""
    keys = set(B8_LIB_KEYS) | {'zprobe-run@.service'} | set(B8_CELL) | {
        'phone_zprobe_verify.py', 'phone_zprobe_rules.py', 'pc_zprobe_refs.sh', 'pc_zprobe_refs_check.py',
        'pc_zprobe_rules.py'}
    pins = read_pins_file(os.path.join(pkg, 'zavod', 'ops', 'zprobe_pins_b8.txt'), keys)
    files = {k: os.path.join(B8_LIB, k) for k in B8_LIB_KEYS}
    files['zprobe-run@.service'] = os.path.join(UNIT_DIR, 'zprobe-run@.service')
    files.update(B8_CELL)
    probs = []
    for k, p in sorted(files.items()):
        try:
            st = os.lstat(p)
        except OSError as x:
            probs.append(f'B8 {p} {type(x).__name__}')
            continue
        if not stat.S_ISREG(st.st_mode):
            probs.append(f'B8 {p} is not a plain file')
        elif REL.sha(p) != pins[k]:
            probs.append(f'B8 {p} differs from B8 pins')
    try:
        rel = open(os.path.join(B8_LIB, 'RELEASE'), 'rb').read()
        if rel != f'commit={pins["release_commit"]}\nversion=3.5.5\n'.encode():
            probs.append('B8 RELEASE differs from the B8 release commit')
    except OSError as x:
        probs.append(f'B8 RELEASE {type(x).__name__}')
    return probs


def account_problems():
    zp, g = REL.get_user('zprobe'), REL.get_group('zprobe')
    if zp is None or g is None:
        return ['user or group zprobe is missing (B8 is not installed)'], None
    probs = []
    if not (0 < zp.pw_uid < REL.SYSTEM_UID_MAX) or not zp.pw_shell.endswith('nologin') or zp.pw_gid != g.gr_gid:
        probs.append('user zprobe is not the system nologin account of B8')
    s = REL.state_dir(DATA, 0o750, zp.pw_uid, zp.pw_gid)
    if s != 'same':
        probs.append(f'data folder: {s}')
    return probs, zp


def started_problems(zp):
    """v0.5 §3: started — настоящая папка zprobe 0750; ровно одна отметка KNOWN_SERIES, её байты = marker с challenge
    из SERIES_START сегмента 000001.jsonl; ничего другого."""
    sd = os.path.join(DATA, 'started')
    s = REL.state_dir(sd, 0o750, zp.pw_uid, zp.pw_gid)
    if s != 'same':
        return [f'started: {s}']
    names = sorted(os.listdir(sd))
    if names != [KNOWN_SERIES]:
        return [f'started must hold exactly [{KNOWN_SERIES}], has {names[:5]}']
    segs = J.read_segments(os.path.join(DATA, 'journal'))
    first = J.json.loads(segs[0][1].split(b'\n')[0]) if segs else {}
    p = os.path.join(sd, KNOWN_SERIES)
    st = os.lstat(p)
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        return ['started mark is not a plain single-link file']
    with open(p, 'rb') as f:
        got = f.read()
    if first.get('series') != KNOWN_SERIES or got != J.marker(KNOWN_SERIES, first.get('challenge')):
        return ['started mark differs from the SERIES_START of 000001.jsonl']
    return []


def journal_problems():
    """Шлюз B9 пп. 1–4 только чтением (orphan нет вовсе) и якорь после pb1trial1."""
    J.JDIR, J.SDIR, J.RUN = os.path.join(DATA, 'journal'), os.path.join(DATA, 'started'), RUN
    try:
        line = J.journal_digest()
    except J.Refused as e:
        return [f'journal gate REFUSED {e.kind}: {e}'], ''
    f = dict(x.split('=', 1) for x in line.split() if '=' in x)
    probs = []
    if len(EXPECT_DIGEST) != 64 or len(EXPECT_LAST) != 64:
        probs.append('expected journal anchor is not the full value (fill it from the read-only server check)')
    if f.get('segments') != str(EXPECT_SEGMENTS) or f.get('seq') != str(EXPECT_SEQ) \
            or not f.get('digest', '').startswith(EXPECT_DIGEST) or not f.get('last_sha256', '').startswith(EXPECT_LAST):
        probs.append('journal differs from the anchor after pb1trial1: ' + line[22:200])
    return probs, line


def units_problems():
    """Службы проб и агента — inactive или нет; заданий systemd для них нет; нет /run/zprobe/*/state.json без
    cleanup.json."""
    probs = []
    rc, out, err = sh('systemctl', 'list-units', '--all', '--no-legend', '--plain', *WATCH_UNITS)
    if rc != 0:
        return [f'systemctl list-units rc={rc} {err.strip()[:80]}']
    for ln in out.split('\n'):
        f = ln.split()
        if len(f) >= 4 and f[2] != 'inactive':
            probs.append(f'unit {f[0]} is {f[2]}/{f[3]}')
    rc, out, err = sh('systemctl', 'list-jobs', '--no-legend', *WATCH_UNITS)
    if rc != 0 or out.strip():
        probs.append(f'systemd jobs for probe units: rc={rc} {out.strip()[:120]}')
    if os.path.isdir(RUN):
        for s in sorted(os.listdir(RUN)):
            d = os.path.join(RUN, s)
            if os.path.lexists(os.path.join(d, 'state.json')) and not os.path.lexists(os.path.join(d, 'cleanup.json')):
                probs.append(f'{d}: state.json without cleanup.json')
    return probs


def common(pkg, rep):
    """Общий список v0.4 §4 (кроме целей). Возвращает учётную запись zprobe или None."""
    for cid, fn in (('B8', lambda: b8_problems(pkg)), ('UNITS', units_problems)):
        p = fn()
        rep.add(cid, 'FAIL' if p else 'OK', '; '.join(p) or '-')
    p, zp = account_problems()
    rep.add('ACCOUNT', 'FAIL' if p else 'OK', '; '.join(p) or f'uid={zp.pw_uid}')
    if zp is None:
        return None
    p, line = journal_problems()
    rep.add('JOURNAL', 'FAIL' if p else 'OK', '; '.join(p) or line)
    p = started_problems(zp)
    rep.add('STARTED', 'FAIL' if p else 'OK', '; '.join(p) or KNOWN_SERIES)
    return zp


def parent_problems(tg):
    """Предки каждой цели — обычные папки root без записи группе и прочим (REL.ancestors) и не точки монтирования.
    Предок, который сам цель B9 (папка LIB), не проверяется как предок: его создаёт эта установка, а его собственные
    предки проверяются по самой папке LIB."""
    own = {path for path, _, _ in tg}
    p = [x for path, _, _ in tg if os.path.dirname(path) not in own for x in REL.ancestors(path)]
    return p + mount_problems([path for path, _, _ in tg])


def preflight(pkg, rep):
    common(pkg, rep)
    tg = targets(pkg)
    there = [p for p, _, _ in tg if os.path.lexists(p)]
    rep.add('TARGETS_ABSENT', 'FAIL' if there else 'OK', ('present: ' + ', '.join(there)) if there else '-')
    p = parent_problems(tg)
    rep.add('PARENTS', 'FAIL' if p else 'OK', '; '.join(sorted(set(p))) or '-')


def target_state(path, data, mode):
    if data is None:
        return REL.state_dir(path, mode, REL.ROOT_UID, REL.ROOT_GID)
    return REL.state_file(path, data, mode, REL.ROOT_UID, REL.ROOT_GID)


def show_problems():
    """M-355-REL32-04: каждое свойство из unit_expect — строго; свойства нет в выводе — тоже отказ."""
    probs = []
    for unit, want in unit_expect().items():
        rc, out, err = sh('systemctl', 'show', unit, *[f'-p{k}' for k in want])
        got = dict(x.split('=', 1) for x in out.split('\n') if '=' in x)
        if rc != 0:
            probs.append(f'{unit} systemctl_show_rc={rc}')
        for k, v in want.items():
            g = got.get(k)
            if g is None:
                ok = False
            elif callable(v):
                ok = v(g)
            elif isinstance(v, list):
                ok = exec_cmds(g) == v
            else:
                ok = g == v
            if not ok:
                probs.append(f'{unit} {k}={g!r}'[:300])
    return probs


def verify_installed(pkg, rep):
    common(pkg, rep)
    bad = [f'{p}: {s}' for p, d, m in targets(pkg) for s in [target_state(p, d, m)] if s != 'same']
    rep.add('TARGETS_SAME', 'FAIL' if bad else 'OK', '; '.join(bad) or '-')
    p = show_problems()
    rep.add('UNITS_LOADED', 'FAIL' if p else 'OK', '; '.join(p) or '-')


def own_record(ev, path):
    """M-355-REL32-02: (намерение, личность, DONE есть?) последней попытки дневника B9 по пути: INTENT, затем CREATED
    и, может быть, DONE. Иначе None (INTENT без CREATED, чужое, ничего)."""
    seq = ev.get(path, [])
    i = max((k for k, (e, _) in enumerate(seq) if e == 'INTENT'), default=None)
    if i is None:
        return None
    after = [e for e, _ in seq[i + 1:]]
    if after not in (['CREATED'], ['CREATED', 'DONE']):
        return None
    return seq[i][1], seq[i + 1][1], after == ['CREATED', 'DONE']


def same_is_own(path, data, mode, rec):
    """M-355-REL32-02: цель с байтами и правами выпуска — своя: дневник называет тот же вид, сумму, размер, права и
    тот же объект (dev, ino); у файла одна ссылка."""
    it, cr, _ = rec
    if data is None:
        want, got = ('dir', mode, 'root'), (it.get('kind'), it.get('mode'), it.get('who'))
    else:
        want = ('file', REL.sha_b(data), len(data), mode)
        got = (it.get('kind'), it.get('sha'), it.get('size'), it.get('mode'))
    st = os.lstat(path)
    return want == got and REL.same_object(st, cr) and (data is None or st.st_nlink == 1)


def plan(pkg):
    """Проход 1 B9: только новые цели или достройка своих по дневнику B9; иное — конфликт. M-355-REL32-02: цель,
    равная выпуску, принимается только если её создал этот выпуск (дневник, тот же inode); чужая — конфликт."""
    ev = REL.read_journal()
    acts, probs = [], []
    for path, data, mode in targets(pkg):
        s = target_state(path, data, mode)
        if s == 'absent':
            acts.append(('dir', path, mode, 'root') if data is None else ('file', path, data, mode, 0))
            continue
        own = own_record(ev, path)
        if s == 'same' and (own is None or not same_is_own(path, data, mode, own)):
            probs.append(f'{path}: equal to the release but not created by this release (journal, inode)')
        elif s == 'same' and own[2]:
            pass                                                           # своя и завершённая (DONE)
        else:
            rec = REL.own_unfinished(ev, path)
            if data is None:
                if REL.resumable_dir(path, rec, mode, 'root', REL.ROOT_UID, REL.ROOT_GID):
                    acts.append(('finish_dir', path, mode, 'root', rec[1]))
                else:
                    probs.append(s)
            else:
                have = REL.resumable_file(path, rec, data, mode)
                if have is None:
                    probs.append(s)
                else:
                    acts.append(('finish_file', path, data, mode, have, rec[1]))
    return acts, probs


def install(pkg, rep):
    lock = REL.install_lock()
    if lock is None:
        print('ZPROBE_B9_INSTALL=REFUSED another install is running; nothing changed')
        return 1
    try:
        zp = common(pkg, rep)
        p = parent_problems(targets(pkg))
        rep.add('PARENTS', 'FAIL' if p else 'OK', '; '.join(sorted(set(p))) or '-')
        if rep.fails or zp is None:
            print(f'ZPROBE_B9_INSTALL=REFUSED checks fails={rep.fails}; nothing created')
            return 1
        acts, probs = plan(pkg)
        if probs or not acts:
            for x in probs:
                print('CONFLICT ' + x)
            print('ZPROBE_B9_INSTALL=REFUSED ' + ('conflicts=%d' % len(probs) if probs else 'already installed')
                  + '; nothing created')
            return 1
        done = []
        os.umask(0o077)
        j = REL.Journal(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        try:
            REL.apply(acts, done, j)
        except Exception as x:  # noqa: BLE001
            print(f'ZPROBE_B9_INSTALL=PARTIAL created={done} journal={j.path} error={type(x).__name__}: {x}; '
                  'nothing removed; run install again: it finishes only objects of this release from the journal')
            return 1
        finally:
            j.close()
        rc0, _, e0 = sh('systemctl', 'daemon-reload')
        rc1, o1, e1 = sh('systemd-analyze', 'verify', *UNIT_SHOW)
        print(f'INSTALLED_NEW={done} journal={j.path} daemon_reload_rc={rc0} verify_rc={rc1} '
              f'{(e0 + o1 + e1).strip()[:200]}')
        rep2 = REL.Report()
        verify_installed(pkg, rep2)
        ok = rc0 == 0 and rc1 == 0 and not rep2.fails
        print('ZPROBE_B9_INSTALL=' + ('OK' if ok else 'REFUSED installed state does not match; nothing removed'))
        return 0 if ok else 1
    finally:
        os.close(lock)


def main():
    a = sys.argv[1:]
    modes = {'preflight': preflight, 'verify-installed': verify_installed}
    ok = os.geteuid() == 0 and ((len(a) == 2 and a[0] in ('preflight', 'verify-installed', 'install')) or
                                (len(a) == 3 and a[0] == 'report' and a[2] in modes))
    if not ok:
        print('usage (root): zprobe_release_b9.py preflight|verify-installed|install <package dir> | '
              'report <package dir> preflight|verify-installed')
        return 2
    pkg = os.path.abspath(a[1])
    rep = REL.Report()
    try:
        if a[0] == 'install':
            return install(pkg, rep)
        modes[a[2] if a[0] == 'report' else a[0]](pkg, rep)
    except Exception as x:  # noqa: BLE001 — всегда явный итог
        print(f'ZPROBE_B9_{a[0].upper()}=FAIL error={type(x).__name__}: {x}')
        return 1
    name = (a[2] if a[0] == 'report' else a[0]).upper().replace('-', '_')
    if a[0] == 'report':
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        path = REL.new_file(os.path.join(REL.JOURNAL_DIR, REL.JOURNAL_PREFIX + '{}.report'), stamp,
                            ('\n'.join(rep.lines) + '\n').encode('utf-8'))
        print(f'REPORT={path} SHA256={REL.sha(path)} (diagnostics, not a permission)')
    print(f'ZPROBE_B9_{name}={"FAIL" if rep.fails else "OK"} fails={rep.fails}')
    return 1 if rep.fails else 0


if __name__ == '__main__':
    sys.exit(main())
