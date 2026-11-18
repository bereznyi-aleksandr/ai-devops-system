#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_runner.py
# ВЕРСИЯ: v0.15 (выпуск B13)  СТАТУС: DRAFT  ДАТА ОБНОВЛЕНИЯ: 2026-11-18 13:19 +02:00
# v0.15 (Claude, терминал zavod; проект DESIGN_B13_RELEASE v0.2, REL125): только имена B13 — папка программ /usr/local/lib/zavod/probes-b13, в PINNED службы
#   zprobe-run-b13@ и zprobe-journal-b13@, TOOL zprobe-runner-b13-0.15; имя формата 'b10' в state/evidence то же.
# v0.14 (Claude, терминал zavod; B13, REL123 M-355-REL123-01): решение шага drop-in вынесено в dropin_verdict() — ОДНО
#   смысловое сравнение (zprobe_dropin v0.2) для decide, cage.props_ok и cage.changed_props; сырые отличия — отдельно,
#   только для разбора (cage.raw_changed_props). Замеры (MemoryAvailable) берутся из DROP.RUNTIME_PROPS и в allowed
#   не входят; allowed = только R.DROPIN_KEYS. props_ok = proceed И result OK И нет extra — противоречие исключено.
# v0.13 (Claude, чат «напарник · 04» (869221b9), помощник; проект B10 v0.18 раздел 7): имена B10 — папка программ
#   /usr/local/lib/zavod/probes-b10, в списке PINNED службы zprobe-run-b10@ и zprobe-journal-b10@; логика та же.
# v0.12 (чат «напарник · 04»): REL64 L-03 — pg() передаёт значения через stdin (команды \set), не в argv psql; REL64 L-02 —
#   mkdirs_sync: fsync родителя после каждой новой папки (папка дополнения и архив копий).
# v0.11 (2026-11-14 23:42 +02:00, чат «напарник · 04», 869221b9; проект B10 v0.18 1.3 и 4.1): state.json формата B10
#   {series, runner, lease, lease_id, dropin}; имя серии, занятое в preserve/archive/seal/export или pb1trial2, —
#   отказ до аренды; строка ZPROBE_LEASE_OPEN до INSERT; сразу после INSERT и до drop-in — anchor_run.json
#   (zprobe_unstarted.take_anchor/write_anchor); start_request_s перед заявкой на запуск; уборка без сессии
#   (session_start NONE) — zprobe_unstarted.seal_unstarted: H1–H10 и общий порядок печати 4.4 → SAFE_PRE_START |
#   BLOCKED_SESSION_UNKNOWN | BLOCKED_STOP_REVIEW (серия в журнале проб всё равно INTERRUPTED).
# v0.10 (2026-11-14 23:29 +02:00, чат «напарник · 03», d6c11f6b; проект B10 v0.18 раздел 2): шаг drop-in решает
#   через zprobe_dropin.decide() — dropin_check.json и строка журнала ДО отказа; в evidence dropin_check (итог, код,
#   diag_status) и cage_partial (п.6); потеря всех каналов → код выхода 75 (п.5в). Каталог LIB и отпечатки B10 —
#   отдельным шагом (сборщик выпуска B10).
# v0.9 (2026-11-14 10:42 +02:00, проект B9 v0.9): программа ставится в /usr/local/lib/zavod/probes-b9; в отпечатки кода
#   серии входят службы B9 zprobe-run-b9@.service и zprobe-journal-b9@.service вместо zprobe-run@.service B8.
# v0.8 (2026-11-14 09:00 +02:00, проба pb1trial1 на zavod-1, дефект D2): put_new ставит права явно (os.fchmod после
#   os.fchown) — UMask=0077 службы срезал 0640 до 0600, и запись журнала (zprobe) не читала evidence.json и cleanup.json.
# v0.7 (2026-11-13 20:17 +02:00, check B7 на zavod-1): таблица nft для фактов cage читается nft -u — meta skuid именами
#   пользователей, как в NFT_EXPECTED (без -u nftables v1.0.9 печатает номера, и правила давали ложный отказ).
# v0.6 (2026-11-13 05:59 +02:00, аудит R5): C-R5-01 в факты cage — номер группы процессов экземпляра (cgroup_id,
#   номер узла каталога в /sys/fs/cgroup; его же ядро отдаёт посреднику по сокету); M-R5-05 строки сеанса собирает
#   R.collect_session — повтор начала, начало без итога, неверная строка — отказ прогона (Abort), не пропуск.
# v0.5 (2026-11-12 23:41 +02:00, аудит R4): окна попыток — метки journald строк PB1_BEGIN и PB1 (их ставит хост,
#   поле window из сеанса не принимается); у записей посредника и строк ядра — метка journald ts; строка ядра
#   несёт адрес источника; в свидетельство — время начала и конца прогона run_utc (для снимков веток компьютера);
#   уборка SAFE только при строке session_start этой аренды (R.SEALED), NONE — BLOCKED_NOT_SEALED.
# v0.4 (2026-11-12 23:14 +02:00, аудит R3): C-R3-02 ничего не удаляется — дополнение остаётся у экземпляра
#   zagent@<аренда> (случайное имя, больше не запускается), его копия идёт в архив, экземпляр маскируется
#   (systemctl mask --runtime), шаблон проверяется по экземпляру-пустышке; M-R3-03 серия получает итог RUN_DONE,
#   COMPLETE ставит журнал только после уборки SAFE (cleanup.json); M-R3-02 в свидетельство идут сырые
#   IPAddressDeny/IPAddressAllow и таблица nft, правила проверяют их сами; M-R3-04 строки отказа ядра nft.
# ДАТА СОЗДАНИЯ: 2026-11-12 19:23 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-15 19:58 +02:00
# REL75 (M-355-REL75-01): drop-in сеанса запускает python3 -I -B (байт-код в папку программ не пишется).
#   опись без обрезки и пропусков DNS; M-03 запись без замены O_EXCL, архив копией в новый файл; M-04 след аренды до
#   записи в базу, cleanup находит аренду по держателю и не пишет «очищено» при неудачной остановке)
# ИСПОЛНИТЕЛЬ: Claude (чаты 87eee078-952e-4855-8936-7f4d449aa9ac, c7307e9c-8e0e-4e24-997c-12d9fd3b0c71)
# НАЗНАЧЕНИЕ: привилегированная часть службы прогона проб zprobe-run@<серия>.service (строки ExecStartPre=+ и
#   ExecStopPost=+; DESIGN_3_5_5_PB1_v0_2.md, раздел 3; аудит ChatGPT STAGE355 R1: C-02, M-06, M-07, M-08, M-09).
#   run <серия>: опись адресов GitHub снаружи клетки (DNS хоста ∩ GitHub meta), здоровье посредника, контроль TCP
#   с хоста до и после, пробная аренда, временное дополнение ТОЛЬКО этой аренды в /run, сверка свойств службы,
#   проверка клетки во время работы (uid, cgroup, точки монтирования, фильтр inet zavod, список адресов службы),
#   сбор строк сеанса из journald только по доверенным полям (_SYSTEMD_INVOCATION_ID, _PID, _UID), журнал
#   посредника по его доверенным полям, остановка, перенос дополнения в архив, сверка возврата. Итог — файл
#   /run/zprobe/<серия>/evidence.json (root:zprobe 0640). Исходы попыток не ставит: это делает zprobe_journal.py
#   по zprobe_rules.py. cleanup <серия>: аварийный путь — остановить аренду, перенести дополнение в архив.
# ОГРАНИЧЕНИЯ: ничего не удаляет (дополнение — mv в /var/lib/zavod/probes/archive/<серия>/); ключей не читает;
#   в GitHub не пишет; сеть хоста — только чтение GitHub meta и соединения TCP без данных.
import base64
import datetime
import hashlib
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, '/usr/local/lib/zavod/probes-b13')
import zprobe_rules as R  # noqa: E402
import zprobe_dropin as DROP  # noqa: E402
import zprobe_checks as C  # noqa: E402
import zprobe_seal as SEAL  # noqa: E402
import zprobe_unstarted as UN  # noqa: E402

RUNTIME_KEYS = DROP.RUNTIME_PROPS   # B13: доказанный замер (CI 44282558463) — классифицируется в zprobe_dropin

LIB = '/usr/local/lib/zavod/probes-b13'
RUN = '/run/zprobe'
ARCH = '/var/lib/zavod/probes/archive'
PINNED = ('pb1_session.py', 'zprobe_rules.py', 'zprobe_runner.py', 'zprobe_journal.py', 'zprobe-start',
          '/etc/systemd/system/zprobe-run-b13@.service', '/etc/systemd/system/zprobe-journal-b13@.service',
          '/etc/systemd/system/zagent@.service',
          '/usr/local/lib/zavod/zavod-proxy', '/usr/local/lib/zavod/zavod-gate', '/etc/zavod/zavod-egress.nft')
SESSION_UIDS = range(61184, 65520)
DUMMY = 'zagent@' + '0' * 32 + '.service'   # R3 C-02: экземпляр-пустышка — по нему видно, что шаблон не задет
TERMINAL = R.SEALED   # R4 M-02: строка session_start есть — её ключ lease_id навсегда закрывает новый запуск
PSQL = ['runuser', '-u', 'postgres', '--', 'psql', '-X', '-A', '-t', '-q', '-v', 'ON_ERROR_STOP=1', '-d', 'bem']
# 1.3: места прежних серий — имя, которое там уже есть, новая серия B10 не получает (две пробы под одним именем)
TAKEN_PLACES = ('/var/lib/zavod/preserve', ARCH, '/var/lib/zavod/seal', '/var/lib/zavod/export')
INSTALLED = os.path.join(LIB, 'INSTALLED.sha256')   # список установленных файлов B10 (пишет установщик B10)
TOOL = 'zprobe-runner-b13-0.15'


class Abort(Exception):
    pass


def sh(*args, timeout=30, check=True, inp=None):
    p = subprocess.run(list(args), capture_output=True, text=True, timeout=timeout, input=inp)
    if check and p.returncode != 0:
        raise Abort(f'{args[0]}_rc_{p.returncode}')
    return p.stdout


PG_VALUE = re.compile(r'[0-9A-Za-z_-]{1,64}')


def pg(q, **v):
    """REL64 L-03: значения (номер аренды, держатель, коммит) — только через stdin командами \\set, не в argv psql
    (argv виден в журнале и в событиях PAM). Значение вне [0-9A-Za-z_-]{1,64} — отказ без вызова."""
    for k, x in v.items():
        if not PG_VALUE.fullmatch(str(k)) or not PG_VALUE.fullmatch(str(x)):
            raise Abort(f'pg_value_{k}')
    head = ''.join(f"\\set {k} '{x}'\n" for k, x in v.items())
    return sh(*PSQL, inp=head + q + '\n').strip()


def mkdirs_sync(path, mode):
    """REL64 L-02: как os.makedirs(exist_ok=True), но после каждой новой папки — fsync её родителя."""
    cur = '/'
    for part in [x for x in path.split('/') if x]:
        parent, cur = cur, os.path.join(cur, part)
        try:
            os.mkdir(cur, mode)
        except FileExistsError:
            continue
        fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def sha_file(p):
    with open(p, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def show(unit, *props):
    out = sh('systemctl', 'show', unit, *sum((['-p', p] for p in props), []))
    return dict(ln.split('=', 1) for ln in out.splitlines() if '=' in ln)


def put_new(path, data, mode, gid=0):
    """Записать файл, которого ещё нет (R2 M-03): O_CREAT|O_EXCL — ядро атомарно отказывает, если имя уже есть;
    без временного файла и без переименования, поэтому заменить чужой файл нельзя. Недописанный файл читатели
    (cleanup) распознают как испорченный JSON и идут резервным путём по базе."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    except FileExistsError:
        raise Abort('exists_' + os.path.basename(path))
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        os.fchown(f.fileno(), 0, gid)
        os.fchmod(f.fileno(), mode)   # D2: маска процесса (UMask службы) не должна срезать права читателя
        f.write(data)   # недописанный файл читатель распознаёт как испорченный JSON → итог INTERRUPTED
        f.flush()
        os.fsync(f.fileno())


def tcp_ok(ip, port):
    try:
        with socket.create_connection((ip, port), timeout=5):
            return True
    except OSError:
        return False


def snapshot_targets():
    req = urllib.request.Request('https://api.github.com/meta', headers={'User-Agent': 'zavod-probe'})
    with urllib.request.urlopen(req, timeout=20) as r:
        body = r.read()
    meta = json.loads(body)
    nets = [ipaddress.ip_network(n) for key in ('web', 'api', 'git') for n in meta.get(key, [])]
    dns = {}
    for name in R.GH_NAMES:          # R2 C-02: любой сбой DNS по любому имени — серия прерывается, без пропусков
        try:
            got = sorted({str(ipaddress.ip_address(i[4][0])) for i in socket.getaddrinfo(name, 443, type=socket.SOCK_STREAM)})
        except (OSError, ValueError) as e:
            raise Abort(f'dns_failed_{name}_{type(e).__name__}')
        if not got:
            raise Abort(f'dns_empty_{name}')
        dns[name] = got
    targets = R.canonical_targets(dns)   # полная опись, испытываются все адреса, никакой обрезки
    outside = [ip for ip in targets if not any(ipaddress.ip_address(ip) in n for n in nets)]
    if outside:
        raise Abort('dns_outside_github_meta_' + R.ip_tag(outside[0]))   # неоднозначная опись — не молчим
    if not any(':' not in ip for ip in targets):
        raise Abort('no_github_ipv4')
    if len(targets) > R.MAX_TARGETS:
        raise Abort(f'inventory_{len(targets)}_exceeds_{R.MAX_TARGETS}')
    return targets, dns, hashlib.sha256(body).hexdigest()


def proxy_probe_from_host():
    with socket.create_connection(('127.0.0.2', 3128), timeout=10) as s:
        lport = s.getsockname()[1]
        s.sendall(b'CONNECT github.com:443 HTTP/1.1\r\nHost: github.com:443\r\n\r\n')
        data = s.recv(100)
    m = re.match(rb'HTTP/1\.[01] (\d{3}) ', data)
    return lport, int(m.group(1)) if m else None


def journal(*filters, since):
    out = sh('journalctl', '--no-pager', '-o', 'json', '--since', since, *filters, timeout=60)
    return [json.loads(ln) for ln in out.splitlines() if ln.strip()]


def dropin_verdict(p_before, p_after, d_before, d_after, text, sysv, at, path):
    """B13: единственное место решения шага drop-in. Возвращает (dec, cage); cage.props_ok и cage.changed_props
    берутся из того же документа, что и dec.proceed, — расхождение между ними невозможно."""
    dec = DROP.decide(p_before, p_after, R.DROPIN_KEYS, sysv, at, path)
    doc = dec['doc']
    cage = {'dropin_sha256': hashlib.sha256(text.encode()).hexdigest(), 'changed_props': list(doc['changed']),
            'raw_changed_props': list(doc['raw_changed']),
            'props_ok': bool(dec['proceed'] and doc['result'] == 'OK' and not doc['extra']), 'dropin_ok': True,
            'isolated_ok': d_before == d_after and bool(d_after.get('ExecStart'))}
    return dec, cage


def run(series, ev):
    d = os.path.join(RUN, series)
    with open(os.path.join(d, 'request.json'), encoding='utf-8') as f:
        req = json.load(f)
    if req.get('series') != series or req.get('probes') != R.PROBES or not re.fullmatch(r'[0-9a-f]{32}',
                                                                                         req.get('challenge', '')):
        raise Abort('bad_request')
    ev.update(challenge=req['challenge'], probes=req['probes'], status='RUNNING', step='pins',
              gh_names=list(R.GH_NAMES), cred_paths=list(R.CRED_PATHS))
    ev['code_sha256'] = {os.path.basename(p): sha_file(p if p.startswith('/') else os.path.join(LIB, p))
                         for p in PINNED}
    with open(os.path.join(LIB, 'RELEASE'), encoding='ascii') as f:
        ev['release'] = dict(ln.strip().split('=', 1) for ln in f if '=' in ln)
    ev['env'] = {'kernel': os.uname().release, 'host': socket.gethostname(),
                 'systemd': sh('systemctl', '--version').splitlines()[0], 'python': sys.version.split()[0],
                 'git': sh('git', '--version', check=False).strip() or 'absent'}
    now = datetime.datetime.now(datetime.timezone.utc)
    since = now.strftime('%Y-%m-%d %H:%M:%S UTC')
    ev['since'] = since
    ev['run_utc'] = [now.strftime('%Y-%m-%dT%H:%M:%SZ'), None]   # R4 M-01: границы прогона для снимков веток
    ev['step'] = 'targets'
    ev['targets'], ev['dns'], ev['meta_sha256'] = snapshot_targets()
    host_v6 = bool(sh('ip', '-6', 'route', 'show', 'default', check=False).strip())
    ev['step'] = 'control_before'
    hp_port, hp_status = proxy_probe_from_host()
    before = {f'{ip}|{p}': tcp_ok(ip, p) for ip in ev['targets'] for p in R.PORTS}
    nft = sh('nft', '-u', 'list', 'table', 'inet', 'zavod')   # v0.7: имена пользователей, не номера

    ev['step'] = 'lease'
    if UN.series_taken(series, TAKEN_PLACES):
        raise Abort('series_taken')        # 1.3: до аренды, ничего не создано
    lid = sh('cat', '/proc/sys/kernel/random/uuid').strip()
    L = lid.replace('-', '')
    st = {'series': series, 'runner': 'b10', 'lease': L, 'lease_id': lid,
          'dropin': f'/run/systemd/system/zagent@{L}.service.d/50-zprobe.conf'}
    put_new(os.path.join(d, 'state.json'), json.dumps(st), 0o600)   # R2 M-04: след аренды — ДО записи в базу
    if not DROP.emit(UN.lease_open_line(series, lid)):
        raise Abort('lease_open_unlogged')  # 1.3 H2-B10: строка открытия — до INSERT, иначе аренды нет
    pg("INSERT INTO bem_control.chat_lease (lease_id, tenant_id, role_key, chat_number, generation, work_item_id, "
       "holder_session, rules_commit, code_commit, status, opened_by) VALUES (:'id', gen_random_uuid(), "
       "'01_install_probe', 'P00001', 1, gen_random_uuid(), :'holder', :'commit', :'commit', 'OPEN', 'zprobe-run')",
       id=lid, holder='zprobe-' + series, commit=ev['release']['commit'])
    after_s = int(time.time())             # не раньше opened_at: INSERT уже завершён
    ev['lease'] = L
    ev['step'] = 'anchor'                  # 1.3 H9 б: якорь — сразу после аренды, до drop-in и заявки на запуск
    with open('/proc/sys/kernel/random/boot_id', encoding='ascii') as f:
        boot = f.read().strip().replace('-', '')
    try:
        doc = UN.take_anchor(series, lid, after_s, boot, UN.now_utc)
        sfd = UN.open_src(d)
        try:
            ev['anchor_sha256'] = UN.write_anchor(sfd, doc)
        finally:
            os.close(sfd)
    except (SEAL.Refused, OSError) as e:
        raise Abort('anchor_' + str(e)[:60])
    unit = f'zagent@{L}.service'
    ddir = f'/run/systemd/system/{unit}.d'
    if st['dropin'] != ddir + '/50-zprobe.conf':
        raise Abort('dropin_path_mismatch')

    ev['step'] = 'dropin'
    p_before = show(unit)
    d_before = show(DUMMY, 'ExecStart', 'DropInPaths')
    plan = {'challenge': req['challenge'], 'targets': ev['targets'], 'gh_names': ev['gh_names'],
            'cred_paths': ev['cred_paths'], 'cred_env_re': R.CRED_ENV.pattern,
            'repo_https': 'https://github.com/zavod-bereznyi/zavod-work.git', 'repo_path': 'zavod-bereznyi/zavod-work.git'}
    b64 = base64.b64encode(json.dumps(plan, sort_keys=True).encode()).decode()
    text = ('[Service]\nExecStart=\nExecStart=/usr/bin/python3 -I -B ' + LIB + '/pb1_session.py ' + b64 + '\n')
    mkdirs_sync(ddir, 0o755)
    put_new(st['dropin'], text, 0o644)
    sh('systemctl', 'daemon-reload')
    p_after = show(unit)
    d_after = show(DUMMY, 'ExecStart', 'DropInPaths')
    at = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    sysv = (sh('systemctl', '--version').splitlines() or ['?'])[0][:80]
    dec, cage = dropin_verdict(p_before, p_after, d_before, d_after, text, sysv, at, os.path.join(d, 'dropin_check.json'))
    ev['dropin_check'] = {'result': dec['doc']['result'], 'code': dec['code'], 'diag_status': dec['diag_status'],
                          'logged': dec['logged']}
    ev['diag_status'] = dec['diag_status']
    if dec['exit_code']:
        ev['exit_code'] = dec['exit_code']
    if not dec['proceed']:
        ev['cage_partial'] = cage    # раздел 2 п.6: шаг отказа и уже собранное, без значений свойств
        raise Abort(dec['abort'])

    ev['step'] = 'start'
    ev['start_request_s'] = int(time.time())   # 1.3 H9 в: якорь не позже первой заявки на запуск
    sh('runuser', '-u', 'zkernel', '--', 'touch', f'/run/zavod/start/{L}')
    for _ in range(24):
        sh('systemctl', 'start', 'zagent-start.service', check=False, timeout=60)
        if sh('systemctl', 'is-active', unit, check=False).strip() == 'active':
            break
        time.sleep(5)
    else:
        raise Abort('session_not_started')
    s = show(unit, 'InvocationID', 'MainPID', 'ControlGroup', 'IPAddressDeny', 'IPAddressAllow', 'InaccessiblePaths')
    pid, inv = int(s['MainPID']), s['InvocationID']
    with open(f'/proc/{pid}/status', encoding='ascii') as f:
        uid = int(re.search(r'^Uid:\s+(\d+)', f.read(), re.M).group(1))
    with open(f'/proc/{pid}/cgroup', encoding='ascii') as f:
        cg = f.read()
    with open(f'/proc/{pid}/mountinfo', encoding='utf-8') as f:
        mounts = {ln.split()[4] for ln in f}
    need = [p.lstrip('-') for p in s['InaccessiblePaths'].split() if os.path.exists(p.lstrip('-'))]
    cage.update(unit=unit, invocation=inv, pid=pid, uid=uid, cgroup=s['ControlGroup'],
                cgroup_id=os.stat('/sys/fs/cgroup' + s['ControlGroup']).st_ino,
                unit_ok=True, uid_ok=uid in SESSION_UIDS, cgroup_ok=cg.strip().endswith(s['ControlGroup']),
                invocation_ok=bool(re.fullmatch(r'[0-9a-f]{32}', inv)),
                mounts_ok=bool(need) and all(p in mounts for p in need), mounts_need=need,
                nft_table=nft, nft_sha256=hashlib.sha256(nft.encode()).hexdigest(),
                ipacl=[s['IPAddressDeny'], s['IPAddressAllow']])

    ev['step'] = 'collect'
    attempts, done = [], False
    for _ in range(60):
        lines = journal(f'_SYSTEMD_INVOCATION_ID={inv}', since=since)
        mine = [e for e in lines if e.get('_SYSTEMD_UNIT') == unit and e.get('_PID') == str(pid)
                and e.get('_UID') == str(uid) and isinstance(e.get('MESSAGE'), str)]
        done = any(e['MESSAGE'] == 'PB1_DONE' for e in mine)
        if done:
            # R5 M-05: строгий разбор одной функцией правил; метка — journald при приёме строки, не сеанс
            attempts, bad = R.collect_session([(e['MESSAGE'], int(e['__REALTIME_TIMESTAMP'])) for e in mine])
            if bad:
                raise Abort(bad)
            break
        time.sleep(5)
    if not done:
        raise Abort('session_not_done')

    ev['step'] = 'stop'
    pg("SELECT bem_control.lease_mark_running(:'l'::uuid)", l=lid)
    sh('runuser', '-u', 'zkernel', '--', 'touch', f'/run/zavod/stop/{L}')
    for _ in range(24):
        sh('systemctl', 'start', 'zagent-start.service', check=False, timeout=60)
        if sh('systemctl', 'is-active', unit, check=False).strip() != 'active':
            break
        time.sleep(5)
    else:
        raise Abort('session_not_stopped')
    ev['lease_state'] = pg("SELECT coalesce((SELECT status FROM bem_control.session_start WHERE "
                           "lease_id = :'l'::uuid), 'NONE')", l=lid)

    ev['step'] = 'control_after'
    after = {f'{ip}|{p}': tcp_ok(ip, p) for ip in ev['targets'] for p in R.PORTS}
    zproxy_uid = sh('id', '-u', 'zproxy').strip()
    plog = []
    for e in journal('_SYSTEMD_UNIT=zavod-proxy.service', f'_UID={zproxy_uid}', since=since):
        m = e.get('MESSAGE')
        if isinstance(m, str) and m.startswith('ZAVOD_PROXY {'):
            x = json.loads(m[len('ZAVOD_PROXY '):])
            if isinstance(x, dict):
                x['ts'] = int(e['__REALTIME_TIMESTAMP'])   # R4 C-01: метка journald, не поле посредника
                plog.append(x)
    health = [x for x in plog if x.get('peer', '').rsplit(':', 1)[-1] == str(hp_port)
              and x.get('decision') == 'NOT_A_SESSION' and x.get('uid') == 0]
    ev['control'] = {'tcp': {k: ('OPEN' if before[k] and after[k] else 'CLOSED') for k in before},
                     'host_v6': host_v6,
                     'proxy_health': 'OK' if hp_status == 403 and len(health) == 1 else 'FAILED'}
    ev['proxy_log'] = [x for x in plog if x.get('lease') == L]
    # R3 M-04: отказы фильтра nft пишет ядро — наблюдатель снаружи клетки; сверяются по порту источника.
    klog = []
    for e in journal('_TRANSPORT=kernel', since=since):
        k = R.parse_klog(e.get('MESSAGE'))
        if k:
            k['ts'] = int(e['__REALTIME_TIMESTAMP'])   # R4 M-03: время строки ядра для сверки с окном попытки
            klog.append(k)
    ev['kernel_log'] = klog
    ev['attempts'] = [{'name': 'cage', 'kind': 'cage', 'facts': cage}] + attempts
    ev['run_utc'][1] = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    # R3 M-03: это ещё не COMPLETE — итог серии ставит журнал только после подтверждённой уборки (cleanup SAFE).
    ev['status'], ev['step'] = 'RUN_DONE', 'done'


def keep_copy(series, path):
    """R3 C-02: копия дополнения в НОВЫЙ архивный файл (O_EXCL, номер подбирается, существующий архив не
    заменяется) со сверкой SHA-256. Само дополнение не удаляется и не меняется: оно действует только на экземпляр
    zagent@<эта аренда>, который после остановки маскируется; /run — память, после перезагрузки его нет."""
    try:
        with open(path, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        return 'absent'
    dst = os.path.join(ARCH, series)
    mkdirs_sync(dst, 0o700)
    for n in range(1000):
        tgt = os.path.join(dst, os.path.basename(path) + ('' if n == 0 else f'.{n}'))
        try:
            fd = os.open(tgt, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            continue
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if sha_file(tgt) != hashlib.sha256(data).hexdigest():
            raise Abort('archive_copy_mismatch')
        return tgt
    raise Abort('archive_names_exhausted')


def cleanup(series):
    """ExecStopPost=-+ (всегда, и после удачи, и после сбоя): остановить экземпляр, сохранить копию дополнения,
    замаскировать экземпляр, проверить, что запуск аренды больше невозможен; итог — cleanup.json для журнала.
    Ничего не удаляет и не перезаписывает."""
    d = os.path.join(RUN, series)
    res = {'series': series}
    st = None

    def foreign(status):
        # 1.3: чужая серия (остаток pb1trial2, формат B9, имя прежней серии) — эта уборка её не трогает и не пишет
        res['status'] = status
        print('ZPROBE_CLEANUP ' + json.dumps(res, sort_keys=True), flush=True)
        return 3
    if series == C.B9_SERIES:
        return foreign('SERIES_TAKEN')
    try:
        with open(os.path.join(d, 'state.json'), encoding='utf-8') as f:
            st = json.load(f)
        res['found_by'] = 'state'
        if not isinstance(st, dict) or st.get('runner') != 'b10' or st.get('series') != series:
            return foreign('SERIES_FOREIGN')
    except (OSError, ValueError):
        if UN.series_taken(series, TAKEN_PLACES):
            return foreign('SERIES_TAKEN')
        # R2 M-04: следа нет или он недописан — ищем аренду пробы в базе по держателю серии.
        lid = pg("SELECT coalesce((SELECT lease_id::text FROM bem_control.chat_lease WHERE holder_session = :'h' "
                 "AND opened_by = 'zprobe-run' ORDER BY 1 LIMIT 1), 'none')", h='zprobe-' + series)
        if re.fullmatch(r'[0-9a-f-]{36}', lid):
            L = lid.replace('-', '')
            st = {'lease': L, 'lease_id': lid, 'dropin': f'/run/systemd/system/zagent@{L}.service.d/50-zprobe.conf'}
            res['found_by'] = 'database'
    if st is None:
        res['status'] = 'NO_LEASE'              # ни следа, ни строки в базе — аренды не было
    else:
        unit = f"zagent@{st['lease']}.service"
        res['lease'] = st['lease']
        if sh('systemctl', 'is-active', unit, check=False).strip() not in ('inactive', 'failed', 'unknown'):
            sh('runuser', '-u', 'zkernel', '--', 'touch', f"/run/zavod/stop/{st['lease']}", check=False)
            sh('systemctl', 'stop', unit, check=False, timeout=120)
        res['unit_active_after'] = sh('systemctl', 'is-active', unit, check=False).strip()
        res['lease_db_status'] = pg("SELECT coalesce((SELECT status FROM bem_control.chat_lease WHERE lease_id = "
                                    ":'id'::uuid), 'none')", id=st['lease_id'])
        if res['unit_active_after'] not in ('inactive', 'failed', 'unknown'):
            res['status'] = 'BLOCKED_STOP_FAILED'  # не «безопасно»: нужен разбор
        else:
            try:
                res['kept_copy'] = keep_copy(series, st['dropin'])
            except Abort as e:
                res['kept_copy'] = 'failed_' + str(e)
            sh('systemctl', 'mask', '--runtime', unit, check=False)
            res['load_state'] = show(unit, 'LoadState').get('LoadState')
            res['session_state'] = pg("SELECT coalesce((SELECT status FROM bem_control.session_start WHERE "
                                      "lease_id = :'id'::uuid), 'NONE')", id=st['lease_id'])
            settled = res['load_state'] == 'masked' and not res['kept_copy'].startswith('failed_')
            if settled and res['session_state'] == 'NONE' and st.get('runner') == 'b10':
                # 4.1: отказ до start — H1–H10 и общий порядок печати 4.4; SAFE_PRE_START только при печати
                res['pre_start'] = UN.seal_unstarted(series, st['lease_id'], unstarted_deps(series, st))
                res['status'] = res['pre_start']['status']
            else:
                res['status'] = 'SAFE' if settled and res['session_state'] in TERMINAL else 'BLOCKED_NOT_SEALED'
    print('ZPROBE_CLEANUP ' + json.dumps(res, sort_keys=True), flush=True)
    try:
        gid = int(sh('id', '-g', 'zprobe').strip())
        put_new(os.path.join(d, 'cleanup.json'), json.dumps(res, sort_keys=True), 0o640, gid)
    except (Abort, OSError) as e:
        print('ZPROBE_CLEANUP cannot write cleanup.json: ' + str(e), flush=True)
        return 3
    return 0 if res['status'] in ('NO_LEASE', 'SAFE', 'SAFE_PRE_START') else 3


def unstarted_deps(series, st):
    """Внешние шаги уборки 4.1 для zprobe_unstarted.seal_unstarted: сбор фактов B10 (только чтение), SQL через
    stdin, папка серии по дескриптору; код выхода службы — EXIT_STATUS (systemd для ExecStopPost)."""
    d = os.path.join(RUN, series)
    lid, unit = st['lease_id'], f"zagent@{st['lease']}.service"

    def open_source():
        fd = UN.open_src(d)
        try:
            names = SEAL.matrix('cleanup', SEAL.src_names(fd))
        except BaseException:
            os.close(fd)
            raise
        return fd, d, {n: (None, None) for n in names}

    def collect():
        return C.collect('b10', series, lid, {'state': os.path.join(d, 'state.json'),
                                              'evidence': os.path.join(d, 'evidence.json'),
                                              'anchor': os.path.join(d, UN.ANCHOR),
                                              'fragment_expected': UN.expected_fragment(INSTALLED)})
    return {'exit_status': os.environ.get('EXIT_STATUS'), 'collect': collect,
            'recheck_facts': lambda: C.svc_mask(unit), 'select_row': UN.select_seal, 'call_seal': UN.call_seal,
            'open_source': open_source, 'tool_version': TOOL, 'now_utc': UN.now_utc}


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ('run', 'cleanup') or not re.fullmatch(r'[0-9A-Za-z_-]{1,40}',
                                                                                         sys.argv[2]):
        print('usage: zprobe_runner.py run|cleanup <series>', file=sys.stderr)
        sys.exit(2)
    if os.geteuid() != 0:
        sys.exit('ZPROBE_RUNNER must run as root (ExecStart=+, ExecStopPost=-+)')
    series = sys.argv[2]
    if sys.argv[1] == 'cleanup':
        sys.exit(cleanup(series))     # 3 — заблокировано (остановка не подтверждена), не «очищено»
    out = os.path.join(RUN, series, 'evidence.json')
    gid = int(sh('id', '-g', 'zprobe').strip())
    ev = {'series': series, 'status': 'RUNNING'}
    try:
        run(series, ev)
    except Exception as e:  # noqa: BLE001 — любой сбой записывается как ABORTED; серия в журнал попадает всё равно
        ev.update(status='ABORTED', reason=type(e).__name__ + ':' + str(e)[:200])
    try:
        put_new(out, json.dumps(ev, sort_keys=True, ensure_ascii=True), 0o640, gid)
    except Exception:  # noqa: BLE001 — B10 раздел 2 п.5в: все каналы потеряны → последний канал — код 75
        if ev.get('exit_code') == DROP.EXIT_DIAG_LOST:
            sys.exit(DROP.EXIT_DIAG_LOST)
        raise
    print(f"ZPROBE_RUNNER {ev['status']} series={series} step={ev.get('step')}", flush=True)
    if ev.get('exit_code') == DROP.EXIT_DIAG_LOST:
        sys.exit(DROP.EXIT_DIAG_LOST)
    # Код 0 и при ABORTED: свидетельство записано; после уборки ExecStopPost (zprobe_journal.py commit) внесёт серию.


if __name__ == '__main__':
    main()
