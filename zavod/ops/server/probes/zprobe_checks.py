#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_checks.py
# ВЕРСИЯ: v0.1 (выпуск B10)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-14 23:31 +02:00  ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · напарник · 03» (d6c11f6b)
# ДАТА ОБНОВЛЕНИЯ: 2026-11-14 23:36 +02:00 (ключ H3 t0 -> tzero: ключ значения proof — только буквы и _)
# НАЗНАЧЕНИЕ: проект B10 v0.18 раздел 1.3 — условия H1–H10 «запуска не было», два проверяющих по вызову:
#   'b9' — только остаток pb1trial2 (R2), 'b10' — только уборка серий B10. Решение — чистая функция evaluate(facts)
#   без системы (полностью проверяется тестами); сбор фактов — collect() (только чтение: journalctl, systemctl show,
#   psql SELECT через stdin, чтение файлов по дескриптору). Один и тот же код для уборки 4.1 и R2 1.6.
# ДОПУЩЕНИЯ (на аудит): времена сравниваются в целых секундах (как R0); T0 = opened_at аренды (секунды эпохи);
#   journal_from_cursor = курсор якоря H9 (B9: cursor_after R1; B10: cursor anchor_run), journal_to_cursor —
#   курсор последней записи прохода H5; H8 — только служба аренды (без счёта чужих zagent@).
import datetime
import hashlib
import json
import os
import re
import stat
import subprocess

START_JOB = '7d4958e842da4a758f6c1cdc7b36dcc5'      # systemd: «служба запускается»
LOSS = re.compile(r'suppress|missed|corrupt|truncat|ignoring|unclean|failed to write|no space|disk full')
UNIT_FIELDS = ('UNIT', '_SYSTEMD_UNIT', 'OBJECT_SYSTEMD_UNIT', 'USER_UNIT', '_SYSTEMD_USER_UNIT')
HEX32 = re.compile(r'[0-9a-f]{32}')
HEX64 = re.compile(r'[0-9a-f]{64}')
UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
SERIES = re.compile(r'[0-9A-Za-z_-]{1,40}')
B9_SERIES = 'pb1trial2'
B9_STATE = {'lease', 'lease_id', 'dropin'}
B10_STATE = {'series', 'runner', 'lease', 'lease_id', 'dropin'}
ROLE, OPENED_BY = '01_install_probe', 'zprobe-run'
MAX_LINE = 1 << 20
CHECKS = tuple(f'H{i}' for i in range(1, 11))


def units(fmt, series):
    """Служба пробы своего формата и служба другого формата (её записи → не прошла)."""
    own, other = ('b9', 'b10') if fmt == 'b9' else ('b10', 'b9')
    return f'zprobe-run-{own}@{series}.service', f'zprobe-run-{other}@{series}.service'


def _n(x):
    """Неотрицательное целое для строки значения (формат proof: только цифры)."""
    return str(max(0, int(x)))


def evaluate(f):
    """Решение по фактам. Возвращает {'ok', 'failed', 'checks', 'boot_id', 't0_utc', 'journal_from_cursor',
    'journal_to_cursor'}; checks — H1…H10 {'ok', 'value'} (H9 ещё 'src'). Любой недостающий факт — не прошла."""
    fmt, S, lid = f.get('fmt'), f.get('series'), f.get('lid')
    res = {}

    def put(k, ok, value):
        res[k] = {'ok': bool(ok), 'value': value}

    try:
        L = lid.replace('-', '')
        okargs = fmt in ('b9', 'b10') and SERIES.fullmatch(S) and UUID.fullmatch(lid) \
            and (fmt == 'b10' or S == B9_SERIES) and (fmt == 'b9' or S != B9_SERIES)
    except (AttributeError, TypeError):
        okargs, L = False, ''
    if not okargs:
        return {'ok': False, 'failed': ['ARGS'], 'checks': {}}
    row = f.get('lease_row') or {}
    T0 = row.get('opened_at_s')
    t0ok = type(T0) is int and T0 > 0
    boot = f.get('boot_now')
    dropin = f'/run/systemd/system/zagent@{L}.service.d/50-zprobe.conf'

    # H1 — личность аренды
    st = f.get('state') if isinstance(f.get('state'), dict) else {}
    want = B9_STATE if fmt == 'b9' else B10_STATE
    h1 = set(st) == want and st.get('lease') == L and st.get('lease_id') == lid and st.get('dropin') == dropin \
        and row.get('lease_id') == lid and row.get('holder_session') == 'zprobe-' + S \
        and row.get('opened_by') == OPENED_BY and row.get('role_key') == ROLE and f.get('evidence_lease') == L
    if fmt == 'b10':
        h1 = h1 and st.get('series') == S and st.get('runner') == 'b10'
    else:
        a = f.get('anchor') if isinstance(f.get('anchor'), dict) else {}
        h1 = h1 and HEX64.fullmatch(str(f.get('state_sha_run'))) and f.get('state_sha_run') == f.get(
            'state_sha_manifest') and a.get('series') == S and a.get('lease') == L and a.get('lease_id') == lid \
            and a.get('boot_id') == boot
    put('H1', h1, f'fmt={fmt.upper()} ' + ('OK' if h1 else 'FAIL'))

    # H2 — своё событие открытия и одна загрузка; эталон файла службы
    ue = f.get('unit_entries') or {}
    starts, opens, boots = ue.get('start_jobs') or [], ue.get('lease_open') or [], ue.get('boots') or []
    fr, fe = f.get('fragment') or {}, f.get('fragment_expected') or {}
    h2 = t0ok and len(starts) == 1 and starts[0] <= T0 and list(boots) == [boot] \
        and f.get('other_runner_count') == 0 and fr.get('safe') is True and fr.get('path') \
        and fr.get('path') == fe.get('path') and HEX64.fullmatch(str(fr.get('sha'))) and fr.get('sha') == fe.get('sha')
    if fmt == 'b10':
        h2 = h2 and len(opens) == 1 and opens[0] <= T0
    else:
        since = f.get('evidence_since_s')
        h2 = h2 and type(since) is int and starts[0] <= since <= T0 if h2 else False
    put('H2', h2, f'starts={len(starts)} opens={len(opens)} boots={len(boots)} ' + ('OK' if h2 else 'FAIL'))

    # H3 — перезагрузок не было
    bt = f.get('btime')
    h3 = t0ok and type(bt) is int and HEX32.fullmatch(str(boot)) and bt < T0
    put('H3', h3, f'btime={_n(bt or 0)} tzero={_n(T0 or 0)}')

    # H4 — журнал без провала
    fe_s, mono, jact, vrc = f.get('first_entry_s'), f.get('journald_mono_us'), f.get('journald_active'), \
        f.get('verify_rc')
    h4a = type(fe_s) is int and type(bt) is int and fe_s <= bt + 60
    h4b = jact == 'active' and type(mono) is int and mono > 0 and t0ok and type(bt) is int \
        and bt + mono // 1000000 < T0
    sc = f.get('scan') or {}
    h4c = sc.get('rc') == 0 and sc.get('loss') == 0
    h4 = h4a and h4b and h4c and vrc == 0
    put('H4', h4, f'gap={_n((fe_s or 0) - (bt or 0))} verify={_n(vrc if type(vrc) is int else 99)} '
                  f'loss={_n(sc.get("loss") or 0)} ' + ('OK' if h4 else 'FAIL'))

    # H5 — один проход: есть данные, нет следов службы, zagent-start и чужих упоминаний аренды
    h5 = sc.get('rc') == 0 and type(sc.get('n')) is int and sc['n'] > 0 and sc.get('unit_hits') == 0 \
        and sc.get('start_hits') == 0 and sc.get('other') == 0
    put('H5', h5, f'n={_n(sc.get("n") or 0)} u={_n(sc.get("unit_hits") or 0)} st={_n(sc.get("start_hits") or 0)} '
                  f'oth={_n(sc.get("other") or 0)}')

    # H6 — БД
    db = f.get('db') or {}
    h6 = all(db.get(k) == 0 for k in ('session_start', 'session_start_log', 'gate_command', 'live'))
    put('H6', h6, ' '.join(f'{k}={_n(db.get(v) if type(db.get(v)) is int else 99)}' for k, v in (
        ('ss', 'session_start'), ('ssl', 'session_start_log'), ('gc', 'gate_command'), ('live', 'live'))))

    # H7 — заявок не было
    h7 = f.get('named_files') == 0
    put('H7', h7, f'named={_n(f.get("named_files") if type(f.get("named_files")) is int else 99)}')

    # H8 — служба сейчас
    sv = f.get('svc') or {}
    h8 = sv.get('ActiveState') == 'inactive' and sv.get('InvocationID') == '' and sv.get('ActiveEnterTimestamp') == ''
    put('H8', h8, 'INACTIVE' if h8 else 'ACTIVE_OR_UNKNOWN')

    # H9 — опорная точка: B9 — якорь R1, B10 — anchor_run.json бегунка
    a = f.get('anchor') if isinstance(f.get('anchor'), dict) else {}
    if fmt == 'b9':
        cur, cus = a.get('cursor_after'), a.get('cursor_after_us')
    else:
        cur, cus = a.get('cursor'), a.get('cursor_us')
    tok = type(cus) is int and cus > 0
    h9 = tok and t0ok and a.get('boot_id') == boot and a.get('lease_id') == lid and a.get('series') == S \
        and cus // 1000000 >= T0 and f.get('anchor_cursor_ok') is True and isinstance(cur, str) and cur
    if fmt == 'b10':
        fsr = f.get('first_start_request_s')
        h9 = h9 and (fsr is None or (type(fsr) is int and cus // 1000000 <= fsr))
    put('H9', h9, f'lag={_n(cus // 1000000 - T0) if tok and t0ok else 0} ' + ('OK' if h9 else 'FAIL'))
    res['H9']['src'] = 'r1' if fmt == 'b9' else 'run'

    # H10 — маска на месте
    m = f.get('mask') or {}
    h10 = m.get('link') == '/dev/null' and m.get('LoadState') == 'masked' and m.get('UnitFileState') == \
        'masked-runtime' and m.get('etc_exists') is False
    put('H10', h10, 'MASKED' if h10 else 'MASK_FAIL')

    failed = [k for k in CHECKS if not res[k]['ok']]
    out = {'ok': not failed, 'failed': failed, 'checks': res, 'boot_id': boot, 'journal_from_cursor': cur,
           'journal_to_cursor': sc.get('last_cursor')}
    if t0ok:
        out['t0_utc'] = datetime.datetime.fromtimestamp(T0, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return out


def proof_checks(ev):
    """checks для proof.json: только {'ok': True, 'value'} (+ src у H9); вызывать, когда ev['ok']."""
    if not ev.get('ok'):
        raise ValueError('checks_not_ok')
    return {k: dict(v) for k, v in ev['checks'].items()}


# ---------------------------------------------------------------------------------------------------------------
# Сбор фактов (только чтение). Каждая внешняя команда — свой код; ошибка → факт None, evaluate даст «не прошла».

def _run(args, inp=None, timeout=120):
    p = subprocess.run(args, input=inp, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout


def journal_stream(args, each, timeout=600):
    """journalctl -o json потоком: каждая строка ≤1 МБ разбирается и отдаётся each(запись). Возвращает
    (код, число записей, курсор последней). Вывод не накапливается."""
    p = subprocess.Popen(['journalctl', '-o', 'json', '--no-pager', '-q'] + args, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL)
    n, last = 0, None
    try:
        while True:
            ln = p.stdout.readline(MAX_LINE + 1)
            if not ln:
                break
            if len(ln) > MAX_LINE or not ln.endswith(b'\n'):
                p.kill()
                return 98, n, last
            e = json.loads(ln)
            n += 1
            last = e.get('__CURSOR', last)
            each(e)
        rc = p.wait(timeout=timeout)
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()
        p.stdout.close()
    return rc, n, last


def psql_stdin(sql, **vars_):
    """SELECT через stdin (номер аренды не попадает в командную строку и в журнал); переменные — \\set."""
    head = ''.join(f"\\set {k} '{v}'\n" for k, v in vars_.items() if re.fullmatch(r'[0-9A-Za-z_-]{1,64}', str(v)))
    rc, out = _run(['runuser', '-u', 'postgres', '--', 'psql', '-X', '-A', '-t', '-q', '-v', 'ON_ERROR_STOP=1',
                    '-d', 'bem'], inp=head + sql + '\n')
    if rc != 0:
        raise RuntimeError(f'psql_rc_{rc}')
    return out.strip()


def show(unit, *props):
    rc, out = _run(['systemctl', 'show', unit] + [f'-p{p}' for p in props])
    if rc != 0:
        raise RuntimeError(f'show_rc_{rc}')
    return dict(x.split('=', 1) for x in out.splitlines() if '=' in x)


def read_json_at(path, limit=MAX_LINE):
    """Файл по пути без ссылок на последнем шаге; разбор JSON-объекта. (объект, SHA-256) или (None, None)."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        return None, None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > limit:
            return None, None
        raw = os.read(fd, limit + 1)
    finally:
        os.close(fd)
    try:
        obj = json.loads(raw)
    except ValueError:
        return None, hashlib.sha256(raw).hexdigest()
    return (obj if isinstance(obj, dict) else None), hashlib.sha256(raw).hexdigest()


def collect(fmt, series, lid, sources):
    """Факты для evaluate. sources — пути файлов: {'state', 'evidence', 'anchor', 'manifest_state_sha' (B9),
    'fragment_expected': {'path','sha'}}; сам ничего не пишет."""
    L = lid.replace('-', '')
    U, OTHER = units(fmt, series)
    unit = f'zagent@{L}.service'
    f = {'fmt': fmt, 'series': series, 'lid': lid}
    with open('/proc/sys/kernel/random/boot_id', encoding='ascii') as fh:
        f['boot_now'] = fh.read().strip().replace('-', '')
    with open('/proc/stat', encoding='ascii') as fh:
        f['btime'] = next(int(x.split()[1]) for x in fh if x.startswith('btime '))
    row = psql_stdin("SELECT json_build_object('lease_id', lease_id, 'status', status, 'holder_session', "
                     "holder_session, 'opened_by', opened_by, 'role_key', role_key, 'opened_at_s', "
                     "floor(extract(epoch FROM opened_at))::bigint) FROM bem_control.chat_lease "
                     "WHERE lease_id = :'id'::uuid", id=lid)
    f['lease_row'] = json.loads(row) if row else None
    T0 = (f['lease_row'] or {}).get('opened_at_s') or 0
    f['state'], f['state_sha_run'] = read_json_at(sources['state'])
    f['state_sha_manifest'] = sources.get('manifest_state_sha')
    ev, _ = read_json_at(sources['evidence'])
    f['evidence_lease'] = (ev or {}).get('lease')
    try:   # B9 пишет evidence.since строкой '%Y-%m-%d %H:%M:%S UTC' (zprobe_runner.py B9:179)
        f['evidence_since_s'] = int(datetime.datetime.strptime((ev or {}).get('since', ''), '%Y-%m-%d %H:%M:%S UTC')
                                    .replace(tzinfo=datetime.timezone.utc).timestamp())
    except (TypeError, ValueError):
        f['evidence_since_s'] = None
    f['anchor'], _ = read_json_at(sources['anchor'])
    a = f['anchor'] or {}
    cur = a.get('cursor_after') if fmt == 'b9' else a.get('cursor')
    if isinstance(cur, str) and cur:
        got = []
        rc, _, _ = journal_stream([f'--cursor={cur}', '-n', '1'], got.append, timeout=60)
        f['anchor_cursor_ok'] = rc == 0 and len(got) >= 1 and got[0].get('__CURSOR') == cur
    ue = {'start_jobs': [], 'lease_open': [], 'boots': set()}
    lease_open = f'ZPROBE_LEASE_OPEN series={series} lease_id={lid}'

    def on_unit(e):
        ue['boots'].add(e.get('_BOOT_ID'))
        t = int(e.get('__REALTIME_TIMESTAMP', '0')) // 1000000
        if e.get('MESSAGE_ID') == START_JOB and e.get('UNIT') == U and e.get('_PID') == '1':
            ue['start_jobs'].append(t)
        if e.get('_SYSTEMD_UNIT') == U and e.get('MESSAGE') == lease_open:
            ue['lease_open'].append(t)
    rc1, _, _ = journal_stream(['-u', U], on_unit)
    if rc1 == 0:
        ue['boots'] = sorted(ue['boots'])
        f['unit_entries'] = ue
    cnt = [0]
    rc2, _, _ = journal_stream(['-u', OTHER], lambda e: cnt.__setitem__(0, cnt[0] + 1))
    f['other_runner_count'] = cnt[0] if rc2 == 0 else None
    try:
        fp = show(U, 'FragmentPath').get('FragmentPath', '')
        fd = os.open(fp, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            fst = os.fstat(fd)
            data = os.read(fd, MAX_LINE)
        finally:
            os.close(fd)
        f['fragment'] = {'path': fp, 'sha': hashlib.sha256(data).hexdigest(),
                         'safe': stat.S_ISREG(fst.st_mode) and fst.st_uid == 0 and not fst.st_mode & 0o022}
    except (OSError, RuntimeError):
        f['fragment'] = None
    f['fragment_expected'] = sources.get('fragment_expected')
    tmin = []     # H4а: самая ранняя запись первых 120 с загрузки (как R0: минимум времени, не первая строка)

    def on_first(e):
        t = int(e.get('__REALTIME_TIMESTAMP', '0')) // 1000000
        if not tmin or t < tmin[0]:
            tmin[:] = [t]
    rc3, _, _ = journal_stream(['-b', '0', '--until', f"@{f['btime'] + 120}"], on_first)
    f['first_entry_s'] = tmin[0] if rc3 == 0 and tmin else None
    jd = show('systemd-journald.service', 'ActiveState', 'ExecMainStartTimestampMonotonic')
    f['journald_active'] = jd.get('ActiveState')
    mono = jd.get('ExecMainStartTimestampMonotonic', '')
    f['journald_mono_us'] = int(mono) if mono.isdigit() else None
    try:
        f['verify_rc'] = subprocess.run(['journalctl', '--verify', '-q'], capture_output=True, timeout=120).returncode
    except subprocess.TimeoutExpired:
        f['verify_rc'] = 124
    sc = {'unit_hits': 0, 'start_hits': 0, 'loss': 0, 'other': 0}

    def on_scan(e):
        if unit in (e.get(k) for k in UNIT_FIELDS):
            sc['unit_hits'] += 1
        m = e.get('MESSAGE')
        m = m if isinstance(m, str) else str(m)
        if e.get('SYSLOG_IDENTIFIER') == 'systemd-journald' and LOSS.search(m.lower()):
            sc['loss'] += 1
        d = json.dumps(e)
        if L in d or lid in d:
            if e.get('_SYSTEMD_UNIT') == 'zagent-start.service':
                sc['start_hits'] += 1
            elif e.get('_SYSTEMD_UNIT') != U:
                sc['other'] += 1
    sc['rc'], sc['n'], sc['last_cursor'] = journal_stream(['-b', '0', '--since', f'@{T0}'], on_scan)
    f['scan'] = sc
    db = psql_stdin("SELECT json_build_object("
                    "'session_start', (SELECT count(*) FROM bem_control.session_start WHERE lease_id = :'id'::uuid), "
                    "'session_start_log', (SELECT count(*) FROM bem_control.session_start_log WHERE lease_id = "
                    ":'id'::uuid), 'gate_command', (SELECT count(*) FROM bem_control.gate_command WHERE lease_id = "
                    ":'id'::uuid), 'live', (SELECT count(*) FROM bem_control.session_start WHERE lease_id = "
                    ":'id'::uuid AND status IN ('STARTING', 'RUNNING')))", id=lid)
    f['db'] = json.loads(db)
    named = 0
    for d in ('/run/zavod/start', '/run/zavod/stop', '/var/lib/zavod/start-archive', '/var/lib/zavod/start-rejected'):
        try:
            named += sum(1 for n in os.listdir(d) if L in n)
        except FileNotFoundError:
            pass
    f['named_files'] = named
    f['svc'] = show(unit, 'ActiveState', 'InvocationID', 'ActiveEnterTimestamp')
    m = show(unit, 'LoadState', 'UnitFileState')
    try:
        link = os.readlink(f'/run/systemd/system/{unit}')
    except OSError:
        link = None
    m['link'] = link
    m['etc_exists'] = os.path.lexists(f'/etc/systemd/system/{unit}')
    f['mask'] = m
    return f
