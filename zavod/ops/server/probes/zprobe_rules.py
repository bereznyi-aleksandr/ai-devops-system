#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_rules.py
# ВЕРСИЯ: v0.9  СТАТУС: DRAFT
# v0.9 (2026-11-13 11:21 +02:00, CI Zavod Kernel settings.test.mjs): шаблон ISO записан через {2} — тот же смысл, без
#   ложного совпадения с путём диска Windows (буква, двоеточие, обратная косая).
# v0.8 (2026-11-13 07:24 +02:00, аудит R7 C-R7-01): git через посредника — DENIED_POLICY ещё и только если каждый клиент
#   переходника — git этой попытки (peer_problem: PID git из facts.git_pid, цепочка родителей клиента от ядра
#   доходит до него, все имена в цепочке git*, uid клиента = uid сеанса) и в выводе git есть отказ SOCKS5 к
#   github.com с кодом 2 (SOCKS_REFUSED). Иначе NOT_PROVEN: relay_peer_not_git или git_no_socks_refusal.
# v0.7 (2026-11-13 07:08 +02:00, аудит R6B C-R6-01): git через посредника — DENIED_POLICY только если отчёт переходника полон
#   (relay_conns), каждому его соединению ровно одна запись посредника с тем же адресом:портом, NOT_ALLOWED,
#   github.com:443, в окне git, ответ 403; других записей аренды в окне нет; порты не повторяют порты других
#   попыток. Окно и владелец без порта больше не доказывают (NEW_NEGATIVE_R6_N01). CURL_PROXY_403 не используется.
# v0.6 (2026-11-13 05:59 +02:00, аудит R5): C-R5-01 запись посредника принимается, только если ядро назвало её
#   владельца — uid и номер группы процессов (cgroup) сокета — ровно сеансом (они в попытке cage от systemd), адрес
#   собеседника — адрес сеанса, у CONNECT — ещё и порт сеанса целиком; любая запись аренды с чужим владельцем или
#   адресом, повтор порта — NOT_PROVEN всех попыток через посредника; у git порт записи не равен порту ни одной
#   другой попытки; M-R5-02 каждое окно попытки и каждая метка посредника и ядра — внутри run_utc (допуск 2 с);
#   M-R5-05 сбор строк сеанса — одна чистая функция collect_session: повтор PB1_BEGIN, начало без итога, итог без
#   начала, неверная строка — отказ всего прогона; M-R5-01 сверка снимков веток — refs_problem, по времени прогона
#   из самого журнала (её зовут zprobe_verify.py --refs и предварительная проверка компьютера).
# v0.5 (2026-11-12 23:41 +02:00, аудит R4): C-R4-01 запись посредника git — единственная запись аренды внутри окна
#   попытки git (окно — метки journald строк PB1_BEGIN и PB1 сеанса), и каждая запись аренды лежит в окне одной из
#   попыток через посредника; C-R4-02 цепочки output и egress_closed сравниваются целиком с закреплённым списком
#   (никаких return, goto, лишних правил); M-R4-02 уборка SAFE только при строке session_start (её ключ навсегда
#   закрывает запуск аренды, и после перезагрузки тоже); M-R4-03 строка ядра — тот же адрес и порт источника, тот же
#   адрес и порт назначения, метка времени внутри окна попытки; M-R4-04 журнал — отдельные файлы-сегменты.
# v0.4 (2026-11-12 23:14 +02:00, аудит R3): C-R3-01 запись посредника от git push — единственная, не совпавшая
#   по порту ни с одной своей попыткой посредника; M-R3-02 точные IPAddressDeny/IPAddressAllow и порядок правил
#   nft в цепочке output; M-R3-04 отказ tcp подтверждает строка ядра «zavod-egress-refused» с тем же портом
#   источника (наблюдатель снаружи клетки), строки сеанса — номера 1..N подряд; nft reject срабатывает раньше
#   BPF, поэтому стена tcp — ECONNREFUSED/EPERM/EACCES только вместе со строкой ядра.
# ДАТА СОЗДАНИЯ: 2026-11-12 19:23 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-12 19:50 +02:00 (v0.3 по аудиту R2: C-01 привязка
#   имени к назначению bind/binding_problem, C-02 полная опись start_problem/canonical_targets, M-07 только EPERM/EACCES
#   при проверенной клетке, L-08 проверка формы)
# ИСПОЛНИТЕЛЬ: Claude (чаты 87eee078-952e-4855-8936-7f4d449aa9ac, c7307e9c-8e0e-4e24-997c-12d9fd3b0c71)
# НАЗНАЧЕНИЕ: единые правила пробы ПБ-1 (проект DESIGN_3_5_5_PB1_v0_2.md, разделы 4–6; аудит ChatGPT STAGE355 R1:
#   C-01, M-03, M-05, L-10). Один файл для сервера (zprobe_journal.py) и телефона (zprobe_verify.py): каноническая
#   матрица попыток и решение «исход» по сырым фактам. Исход DENIED_POLICY ставится только при конкретном признаке
#   стены И подтверждении снаружи клетки (контроль хоста, журнал посредника); любой иной отказ — NOT_PROVEN.
#   Сеанс сам исход не ставит: он печатает только факты.
# ОГРАНИЧЕНИЯ: только стандартная библиотека; ничего не читает и не пишет; одинаков на сервере и в Termux.
import hashlib
import ipaddress
import json
import re

PROBES = ['ПБ-1']
OUTCOMES = ('DENIED_POLICY', 'ABSENT', 'OPEN', 'NOT_PROVEN', 'OK')
GH_NAMES = ('github.com', 'api.github.com', 'uploads.github.com', 'codeload.github.com', 'gist.github.com',
            'objects.githubusercontent.com', 'raw.githubusercontent.com', 'ghcr.io')
CRED_ENV = re.compile(r'(TOKEN|GITHUB|^GH_|ASKPASS|SSH_AUTH_SOCK|GIT_SSH|CREDENTIAL|_KEY$|SECRET|PASSWORD)', re.I)
CRED_PATHS = ('/etc/zavod', '/etc/zavod/secrets/zgithub', '/var/lib/zavod', '/var/lib/zavod/svc/zgithub',
              '/run/zavod', '/run/postgresql', '/run/dbus', '/run/systemd/resolve', '/root',
              '/home', '/etc/ssh/ssh_host_ed25519_key')
WALL_ERRNO = ('ECONNREFUSED', 'EPERM', 'EACCES')
# R2 M-07 / R3 M-04: код ошибки сам источник не называет (сброс мог прийти снаружи). Стена доказана, только если
# у ядра есть ровно одна строка отказа nft «zavod-egress-refused» с этим адресом, портом и портом источника.
KLOG_PREFIX = 'zavod-egress-refused '
# R4 C-02: полный закреплённый список правил двух цепочек таблицы inet zavod (из cell/zavod-egress.nft, проверку
# совпадения делает CI). Загруженная таблица обязана совпасть построчно: любое лишнее правило (return, goto, jump,
# accept), пропуск или перестановка — NOT_PROVEN.
NFT_EXPECTED = {
    'egress_closed': [
        'counter log prefix "zavod-egress-refused " level warn',
        'meta l4proto tcp reject with tcp reset',
        'reject with icmpx admin-prohibited'],
    'output': [
        'type filter hook output priority filter; policy accept;',
        'ct state established,related accept',
        'meta skuid { "zdb", "zgate", "zquarantine", "zimport", "zbrowser", "zflowable" } jump egress_closed',
        'meta skuid 61184-65519 oifname "lo" ip daddr 127.0.0.2 tcp dport 3128 accept',
        'meta skuid 61184-65519 jump egress_closed',
        'meta skuid "zproxy" oifname "lo" ip daddr 127.0.0.53 meta l4proto { tcp, udp } th dport 53 accept',
        'meta skuid "zproxy" tcp dport 443 accept',
        'meta skuid "zproxy" jump egress_closed',
        'meta skuid "zkernel" oifname "lo" ip daddr 127.0.0.1 tcp dport 8091 accept',
        'meta skuid "zkernel" jump egress_closed',
        'meta skuid { "zgithub", "ztelegram", "zbackup" } oifname "lo" ip daddr 127.0.0.53 meta l4proto { tcp, udp } '
        'th dport 53 accept',
        'meta skuid { "zgithub", "ztelegram", "zbackup" } tcp dport 443 accept',
        'meta skuid { "zgithub", "ztelegram", "zbackup" } jump egress_closed']}
SEALED = ('INTERRUPTED', 'ENDED', 'START_FAILED')   # строка session_start есть — повторный запуск аренды невозможен
SEG_NAME = re.compile(r'\A(\d{6})\.jsonl\Z')
SERIES_NAME = re.compile(r'\A[0-9A-Za-z_-]{1,40}\Z')
ZERO = '0' * 64
ISO = re.compile(r'\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z')
RUN_TOL_US = 2_000_000   # R5 M-02: run_utc с точностью до секунды; окна и метки journald — внутри с допуском 2 с
REFS_REPO = 'https://github.com/zavod-bereznyi/zavod-work'
REFS_PREFIX = 'refs/heads/zprobe/*'
REFS_GAP = 1800          # секунд: снимок «до» не раньше чем за 30 минут до прогона, «после» — не позже 30 минут после
IPACL_DENY = ('0.0.0.0/0', '::/0')
IPACL_ALLOW = ('127.0.0.2/32',)
LOCAL_MS = 1000          # местный отказ фильтра мгновенный; дольше — не доказано
PORTS = (22, 443)
# Свойства службы, которые дополнение пробы вправе изменить (аудит M-08); любое другое отличие — клетка не та.
DROPIN_KEYS = {'ExecStart', 'ExecStartEx', 'DropInPaths'}
CURL_PROXY_403 = 'CONNECT tunnel failed, response 403'
CURL_FAIL = re.compile(r'(?:Immediate connect fail for|connect to) ([0-9a-fA-F.:]+)(?: port \d+)?: '
                       r'(Connection refused|Operation not permitted|Permission denied|No route to host)')
CURL_CONNECTED = re.compile(r'\bConnected to \S+ \(([0-9a-fA-F.:]+)\)')
SSH_FAIL = re.compile(r'connect to host ([0-9a-fA-F.:]+) port 22: '
                      r'(Connection refused|Operation not permitted|Permission denied|No route to host)')
NAME = re.compile(r'\A[a-z0-9_.:-]{1,80}\Z')


MAX_TARGETS = 48        # больше адресов — серия прерывается (R2 C-02: никаких молчаливых обрезаний)


def ip_tag(ip):
    return ip.replace(':', '-')


def fam(ip):
    return 'v6' if ':' in ip else 'v4'


def canonical_targets(dns):
    """Полная опись адресов (R2 C-02): объединение ответов DNS по всем GH_NAMES, без обрезки; v4, затем v6."""
    ips = list(dict.fromkeys(ip for n in GH_NAMES for ip in dns[n]))
    return [i for i in ips if ':' not in i] + [i for i in ips if ':' in i]


def _ip_ok(x):
    try:
        ipaddress.ip_address(x)
        return isinstance(x, str) and x == str(ipaddress.ip_address(x))
    except (ValueError, TypeError):
        return False


def start_problem(start):
    """Проверка формы и полноты SERIES_START до построения матрицы (R2 C-01, C-02, L-08). None — порядок."""
    if not isinstance(start, dict):
        return 'start is not an object'
    if start.get('cred_paths') != list(CRED_PATHS):
        return 'cred_paths differ from the fixed list'
    if start.get('gh_names') != list(GH_NAMES):
        return 'gh_names differ from the fixed list'
    dns = start.get('dns')
    if not isinstance(dns, dict) or sorted(dns) != sorted(GH_NAMES):
        return 'dns snapshot must cover exactly the fixed names'
    for n in GH_NAMES:
        v = dns[n]
        if not isinstance(v, list) or not v or not all(_ip_ok(i) for i in v):
            return f'dns answer for {n} is empty, failed or malformed'
    t = start.get('targets')
    if not isinstance(t, list) or not all(_ip_ok(i) for i in t):
        return 'targets malformed'
    if t != canonical_targets(dns):
        return 'targets are not the full DNS inventory'
    if not any(':' not in i for i in t) or len(t) > MAX_TARGETS:
        return 'inventory has no IPv4 or exceeds the limit'
    c = start.get('control')
    if not isinstance(c, dict) or not isinstance(c.get('tcp'), dict) or not isinstance(c.get('host_v6'), bool):
        return 'control malformed'
    pl = start.get('proxy_log')
    if not isinstance(pl, list) or not all(isinstance(e, dict) for e in pl):
        return 'proxy_log malformed'
    if not isinstance(start.get('lease'), str) or not start['lease']:
        return 'lease malformed'
    kl = start.get('kernel_log')
    if not isinstance(kl, list) or not all(isinstance(e, dict) and isinstance(e.get('dst'), str) and
                                           isinstance(e.get('src'), str) and _int(e.get('ts')) and
                                           isinstance(e.get('spt'), int) and isinstance(e.get('dpt'), int)
                                           for e in kl):
        return 'kernel_log malformed'
    if not all(_int(e.get('ts')) and isinstance(e.get('peer'), str) for e in pl):
        return 'proxy_log has no journal time or peer'
    ru = start.get('run_utc')
    if not isinstance(ru, list) or len(ru) != 2 or not all(isinstance(x, str) and ISO.match(x) for x in ru) \
            or not ru[0] <= ru[1]:
        return 'run_utc malformed'
    return None


def _int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def window(a):
    """R4: окно попытки [t0, t1] — метки journald (микросекунды) строк PB1_BEGIN и PB1; ставит хост, не сеанс."""
    w = a.get('window') if isinstance(a, dict) else None
    if isinstance(w, list) and len(w) == 2 and all(_int(x) for x in w) and w[0] < w[1]:
        return w
    return None


def in_window(ts, w):
    return _int(ts) and w is not None and w[0] <= ts <= w[1]


def iso_us(x):
    """'ГГГГ-ММ-ДДTЧЧ:ММ:ССZ' → микросекунды от 1970-01-01 UTC (как __REALTIME_TIMESTAMP journald)."""
    import calendar
    import time as _t
    return calendar.timegm(_t.strptime(x, '%Y-%m-%dT%H:%M:%SZ')) * 1_000_000


def time_problem(start, attempts):
    """R5 M-02: окна попыток и метки посредника и ядра лежат внутри прогона run_utc (допуск RUN_TOL_US)."""
    lo, hi = iso_us(start['run_utc'][0]) - RUN_TOL_US, iso_us(start['run_utc'][1]) + RUN_TOL_US
    stamps = [x for a in attempts if isinstance(a, dict) and a.get('kind') != 'cage' for x in (window(a) or [])]
    stamps += [e['ts'] for e in start['proxy_log']] + [e['ts'] for e in start['kernel_log']]
    if any(not lo <= t <= hi for t in stamps):
        return 'session_outside_run_time'
    return None


def collect_session(msgs):
    """R5 M-05: строки сеанса [(MESSAGE, метка journald)] → (попытки, причина отказа или None). Строгий порядок:
    PB1_BEGIN n → PB1 n, n = 1, 2, …; повтор начала, начало без итога, итог без начала, чужое имя, неверная строка —
    отказ всего прогона (ничего не пропускается молча). PB1_DONE — конец, после него строк нет."""
    atts, cur, done = [], None, False
    for m, ts in msgs:
        if done:
            return atts, 'session_line_after_done'
        if m == 'PB1_DONE':
            done = True
            continue
        if m.startswith('PB1_BEGIN '):
            b = _json(m[len('PB1_BEGIN '):])
            if cur is not None or not isinstance(b, dict) or b.get('seq') != len(atts) + 1 \
                    or not isinstance(b.get('name'), str):
                return atts, 'session_begin_out_of_order'
            cur = (b['seq'], b['name'], ts)
        elif m.startswith('PB1 '):
            a = _json(m[4:])
            if cur is None or not isinstance(a, dict) or a.get('seq') != cur[0] or a.get('name') != cur[1] \
                    or not ts > cur[2]:
                return atts, 'session_result_without_begin'
            a['window'] = [cur[2], ts]       # окно — только от хоста: метки journald двух строк
            atts.append(a)
            cur = None
        else:
            return atts, 'session_line_unknown'
    if cur is not None:
        return atts, 'session_begin_without_result'
    if not done:
        return atts, 'session_not_done'
    return atts, None


def _json(s):
    try:
        return json.loads(s)
    except ValueError:
        return None


def parse_klog(message):
    """Строка ядра «zavod-egress-refused IN= OUT=lo SRC=… DST=… … PROTO=TCP SPT=… DPT=…» → факты или None."""
    if not isinstance(message, str) or not message.startswith(KLOG_PREFIX):
        return None
    kv = dict(p.split('=', 1) for p in message[len(KLOG_PREFIX):].split() if '=' in p)
    try:
        return {'src': str(ipaddress.ip_address(kv['SRC'])), 'dst': str(ipaddress.ip_address(kv['DST'])),
                'proto': kv.get('PROTO'), 'spt': int(kv['SPT']), 'dpt': int(kv['DPT'])}
    except (KeyError, ValueError):
        return None


def ipacl_problem(acl):
    """R3 M-02: действующие списки службы — ровно «запрет всем» и ровно один разрешённый адрес посредника."""
    try:
        deny, allow = acl
        nd = {str(ipaddress.ip_network(x, strict=False)) for x in deny.split()}
        na = {str(ipaddress.ip_network(x, strict=False)) for x in allow.split()}
    except (TypeError, ValueError, AttributeError):
        return 'ipacl_malformed'
    if nd != set(IPACL_DENY):
        return 'ipacl_deny_not_any'
    if na != set(IPACL_ALLOW):
        return 'ipacl_allow_not_exact'
    return None


def _nft_chains(text):
    chains = {}
    for m in re.finditer(r'chain (\w+) \{\n(.*?)\n\s*\}', text, re.S):
        lines = []
        for ln in m.group(2).splitlines():
            ln = re.sub(r'\s+# handle \d+$', '', ln).strip()
            ln = re.sub(r'counter packets \d+ bytes \d+', 'counter', ln)
            if ln and not ln.startswith('#'):
                lines.append(' '.join(ln.split()))
        chains[m.group(1)] = lines
    return chains


def nft_problem(text):
    """R4 C-02: таблица inet zavod одна, в ней ровно по одной цепочке output и egress_closed, и каждая совпадает с
    закреплённым списком NFT_EXPECTED построчно (исчерпывающий список: return, goto, лишний jump или accept — отказ)."""
    if not isinstance(text, str):
        return 'nft_malformed'
    if text.count('table inet zavod {') != 1:
        return 'nft_table_count'
    for name, want in NFT_EXPECTED.items():
        if text.count(f'chain {name} {{') != 1:
            return 'nft_chain_count_' + name
        if _nft_chains(text).get(name) != want:
            return 'nft_chain_differs_' + name
    return None


def series_problem(attempts):
    """R3 M-04: строки сеанса — номера 1..N подряд, имя не повторяется; попытка хоста (cage) без номера."""
    names = [a.get('name') for a in attempts if isinstance(a, dict)]
    if len(names) != len(set(names)):
        return 'duplicate_attempt'
    sess = [a for a in attempts if isinstance(a, dict) and a.get('kind') != 'cage']
    if [a.get('seq') for a in sess] != list(range(1, len(sess) + 1)):
        return 'session_seq_broken'
    ws = [window(a) for a in sess]       # R4: окна попыток есть, идут по порядку и не перекрываются
    if any(w is None for w in ws) or any(ws[i][1] > ws[i + 1][0] for i in range(len(ws) - 1)):
        return 'session_window_broken'
    return None


def proxy_users(attempts, start):
    """Попытки через посредника — по ИМЕНИ из матрицы (bind), не по виду, который назвал сеанс."""
    return [a for a in attempts if isinstance(a, dict) and (a.get('name') == 'push_https_proxy'
                                                             or bind(a.get('name'), start)[0] == 'proxy')]


def unexplained(ctx):
    """R4 C-01: записи посредника этой аренды, не попавшие в окно ни одной попытки через посредника."""
    ws = [window(a) for a in proxy_users(ctx['attempts'], ctx['start'])]
    return [e for e in proxy_hits(ctx['proxy_log'], ctx['lease']) if not any(in_window(e.get('ts'), w) for w in ws)]


def session_src(ctx):
    """R5 C-01: адрес, с которого сеанс ходит к посреднику, — один для всех его попыток через посредника."""
    srcs = set()
    for a in proxy_users(ctx['attempts'], ctx['start']):
        f = a.get('facts') if isinstance(a.get('facts'), dict) else {}
        if a.get('name') == 'push_https_proxy':      # R6 C-01: адрес своих соединений переходника (getsockname)
            for c in relay_conns(f) or [{}]:
                srcs.add(c.get('src'))
        else:
            srcs.add(f.get('src'))
    return srcs.pop() if len(srcs) == 1 and all(isinstance(s, str) and _ip_ok(s) for s in srcs) else None


def relay_conns(f):
    """R6 C-01: соединения переходника git → посредник (pb1_session.Relay) или None, если отчёт переходника
    неполный: ошибка переходника, поток не остановлен, ни одного соединения, у соединения нет точного адреса и порта."""
    r = f.get('relay') if isinstance(f, dict) else None
    if not isinstance(r, dict) or r.get('err') is not None or r.get('alive') is not False:
        return None
    cs = r.get('conns')
    if not isinstance(cs, list) or not cs:
        return None
    for c in cs:
        if not isinstance(c, dict) or not _int(c.get('lport')) or not isinstance(c.get('src'), str):
            return None
    return cs


SOCKS_REFUSED = re.compile(r"SOCKS5 connection to github\.com[^\n]*\(2\)")


def peer_problem(cs, git_pid, uid):
    """R7 C-01: каждый клиент переходника — запущенный git (git_pid) или его потомок: цепочка от ядра (SO_PEERCRED,
    /proc) начинается PID клиента, кончается PID git, все имена git*, uid — сеанса. Иначе причина."""
    if not _int(git_pid) or git_pid <= 1 or not _int(uid):
        return 'relay_peer_not_git'
    for c in cs:
        pr = c.get('peer')
        if not isinstance(pr, dict) or pr.get('chain_ok') is not True or not _int(pr.get('pid')) \
                or pr.get('uid') != uid:
            return 'relay_peer_not_git'
        ch = pr.get('chain')
        if not isinstance(ch, list) or not ch or not all(
                isinstance(x, list) and len(x) == 2 and _int(x[0]) and isinstance(x[1], str) and x[1].startswith('git')
                for x in ch):
            return 'relay_peer_not_git'
        if ch[0][0] != pr['pid'] or ch[-1][0] != git_pid or len({x[0] for x in ch}) != len(ch):
            return 'relay_peer_not_git'
    return None


def owner_problem(ctx):
    """R5 C-01: каждую запись аренды ядро приписало сокету сеанса — uid и cgroup владельца равны uid и cgroup
    экземпляра zagent@<аренда> (их отдаёт systemd, попытка cage), адрес собеседника — адрес сеанса, порты записей
    не повторяются; ни одной записи вне окон своих попыток. Иначе причина — и все попытки через посредника
    NOT_PROVEN."""
    cage = next((a.get('facts') for a in ctx['attempts'] if isinstance(a, dict) and a.get('name') == 'cage'), None)
    if not isinstance(cage, dict) or not _int(cage.get('uid')) or not _int(cage.get('cgroup_id')):
        return 'proxy_owner_unknown'
    src = session_src(ctx)
    if src is None:
        return 'proxy_src_unknown'
    mine = proxy_hits(ctx['proxy_log'], ctx['lease'])
    ports = []
    for e in mine:
        host, _, port = str(e.get('peer')).rpartition(':')
        if e.get('uid') != cage['uid'] or e.get('cgroup') != cage['cgroup_id'] or host != src:
            return 'proxy_foreign_owner'
        ports.append(port)
    if len(ports) != len(set(ports)):
        return 'proxy_port_reused'
    ux = unexplained(ctx)
    if ux:
        return f'proxy_unexplained_{len(ux)}'
    return None


def bind(name, start):
    """Что именно обязана была испытать попытка с этим именем (R2 C-01): вид и точные значения фактов."""
    t = start['targets']
    if name in ('cage', 'cred_env', 'git_prep'):
        return name, {}
    for p in CRED_PATHS:
        if name == 'cred_path_' + p.strip('/').replace('/', '_'):
            return 'cred_path', {'path': p}
    if name == 'push_https_proxy':
        return 'git_push', {'via': 'proxy'}
    if name == 'push_https_direct':
        return 'git_push', {'via': 'direct', 'resolve': list(t)}
    if name == 'push_ssh':
        return 'git_push', {'via': 'ssh'}
    for ip in t:
        for port in PORTS:
            if name == f'tcp_{port}_{ip_tag(ip)}':
                return 'tcp', {'ip': ip, 'port': port}
        if name == 'connect_ip_' + ip_tag(ip):
            return 'proxy', {'mode': 'connect', 'target': (f'[{ip}]' if ':' in ip else ip) + ':443'}
    for n in GH_NAMES:
        if name == 'connect_' + n:
            return 'proxy', {'mode': 'connect', 'target': n + ':443'}
    if name == 'plain_get':
        return 'proxy', {'mode': 'plain', 'target': 'api.github.com'}
    return None, None


def binding_problem(a, start):
    """None — попытка испытала ровно своё назначение; иначе причина (имя, вид или факт не совпали)."""
    if not isinstance(a, dict) or not isinstance(a.get('facts'), dict):
        return 'facts_not_object'
    kind, need = bind(a.get('name'), start)
    if kind is None:
        return 'name_outside_matrix'
    if a.get('kind') != kind:
        return 'kind_mismatch'
    for k, v in need.items():
        if a['facts'].get(k) != v:
            return 'binding_' + k
    if a['name'] == 'push_ssh':
        v4 = [ip for ip in start['targets'] if ':' not in ip][:1]
        if a['facts'].get('absent') is not True and a['facts'].get('ip') != (v4[0] if v4 else None):
            return 'binding_ip'
    return None


def expected(start):
    """Точный упорядоченный перечень попыток серии по записи SERIES_START (L-10: одна каноническая матрица)."""
    t = start['targets']
    names = ['cage', 'cred_env'] + ['cred_path_' + p.strip('/').replace('/', '_') for p in start['cred_paths']]
    names += ['git_prep', 'push_https_proxy', 'push_https_direct', 'push_ssh']
    names += [f'tcp_{port}_{ip_tag(ip)}' for ip in t for port in PORTS]
    names += ['connect_' + n for n in start['gh_names']]
    names += ['connect_ip_' + ip_tag(ip) for ip in first_per_family(t)]
    names += ['plain_get']
    return names


def first_per_family(targets):
    out, seen = [], set()
    for ip in targets:
        if fam(ip) not in seen:
            seen.add(fam(ip))
            out.append(ip)
    return out


def allowed(name):
    if name in ('cage', 'git_prep'):
        return ('OK',)
    if name == 'cred_env':
        return ('ABSENT',)
    if name.startswith('cred_path_') or name == 'push_ssh':
        return ('DENIED_POLICY', 'ABSENT')
    if name.startswith('tcp_'):
        return ('DENIED_POLICY', 'ABSENT')  # ABSENT — только IPv6 при отсутствии IPv6 у самого хоста
    return ('DENIED_POLICY',)


def proxy_hits(plog, lease, **match):
    return [e for e in plog if e.get('lease') == lease and all(e.get(k) == v for k, v in match.items())]


def classify(a, ctx):
    """a — факты попытки (из сеанса или от хоста), ctx — контроль снаружи: lease, control, proxy_log, prior.
    Возвращает (исход, причина). Любой непредусмотренный случай — NOT_PROVEN."""
    try:
        return _classify(a, ctx)
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        return 'NOT_PROVEN', 'bad_facts_' + type(e).__name__


def _classify(a, ctx):
    k, f, c = a['kind'], a['facts'], ctx['control']
    if k == 'cage':
        bad = [x for x in ('unit_ok', 'uid_ok', 'cgroup_ok', 'invocation_ok', 'mounts_ok', 'dropin_ok', 'props_ok',
                           'isolated_ok') if f.get(x) is not True]
        if set(f.get('changed_props', ['?'])) - DROPIN_KEYS:
            bad.append('extra_props')
        bad += [p for p in (ipacl_problem(f.get('ipacl')), nft_problem(f.get('nft_table'))) if p]
        return ('OK', 'cage') if not bad else ('NOT_PROVEN', 'cage_' + bad[0])
    if k == 'cred_env':
        if not isinstance(f['found'], list):
            return 'NOT_PROVEN', 'bad_found'
        return ('ABSENT', 'none') if not f['found'] else ('OPEN', 'present_' + str(len(f['found'])))
    if k == 'cred_path':
        e = f['errno']
        if e == 'opened':
            return 'OPEN', 'opened'
        if e in ('EACCES', 'EPERM'):
            return 'DENIED_POLICY', e
        if e == 'ENOENT':
            return 'ABSENT', e
        return 'NOT_PROVEN', str(e)          # ENOTDIR, ELOOP и прочее — не доказано (аудит M-05)
    if k == 'git_prep':
        ok = all(f.get(s) == 0 for s in ('init', 'add', 'commit', 'rev_parse')) \
            and bool(re.fullmatch(r'[0-9a-f]{40}', f.get('head', ''))) and f.get('config_list') == ''
        return ('OK', 'prepared') if ok else ('NOT_PROVEN', 'prep_failed')
    if k == 'tcp':
        ip, port, e, ms = f['ip'], f['port'], f['errno'], f['ms']
        if e == 'connected':
            return 'OPEN', 'connected'
        ctl = c['tcp'].get(f'{ip}|{port}')
        if fam(ip) == 'v6' and c['host_v6'] is False and e in ('ENETUNREACH', 'EADDRNOTAVAIL'):
            return 'ABSENT', 'no_ipv6_on_host'
        if ctl != 'OPEN':
            return 'NOT_PROVEN', 'no_outside_control'
        if e not in WALL_ERRNO or not isinstance(ms, int) or ms >= LOCAL_MS or ctx['prior'].get('cage') != 'OK':
            return 'NOT_PROVEN', str(e)
        lp, src, w = f.get('lport'), f.get('src'), window(a)
        if not _int(lp):
            return 'NOT_PROVEN', 'no_lport'
        if not isinstance(src, str) or not _ip_ok(src):
            return 'NOT_PROVEN', 'no_src'
        # R4 M-03: четвёрка «адрес и порт источника, адрес и порт назначения» в окне попытки занята только нашим
        # сокетом (ядро не даёт двум сокетам одну четвёрку), поэтому строка ядра с ней — отказ именно этой попытки.
        kh = [x for x in ctx['start']['kernel_log'] if x.get('proto') == 'TCP' and x['spt'] == lp and x['dpt'] == port
              and x['dst'] == str(ipaddress.ip_address(ip)) and x['src'] == str(ipaddress.ip_address(src))
              and in_window(x.get('ts'), w)]
        if len(kh) != 1:
            return 'NOT_PROVEN', f'kernel_log_{len(kh)}'
        return 'DENIED_POLICY', e + '_nft'   # отказ поставил фильтр ядра: строка ядра с этой четвёркой в окне
    if k == 'proxy':
        if c.get('proxy_health') != 'OK':
            return 'NOT_PROVEN', 'proxy_not_healthy'
        st, lp = f['status'], f['lport']
        if isinstance(st, int) and 200 <= st < 300:
            return 'OPEN', f'http_{st}'
        want = {'connect': (403, 'NOT_ALLOWED'), 'plain': (405, 'METHOD_REFUSED')}[f['mode']]
        tgt = f['target'] if f['mode'] == 'connect' else 'http://' + f['target'] + '/'
        bad = owner_problem(ctx)
        if bad:
            return 'NOT_PROVEN', bad
        if not _int(lp) or f.get('src') != session_src(ctx):
            return 'NOT_PROVEN', 'no_lport_or_src'
        hits = [e for e in proxy_hits(ctx['proxy_log'], ctx['lease'], decision=want[1], target=tgt)
                if e.get('peer') == f"{f['src']}:{lp}" and in_window(e.get('ts'), window(a))]   # адрес и порт целиком
        if st == want[0] and len(hits) == 1:
            return 'DENIED_POLICY', f'http_{st}_{want[1]}'
        return 'NOT_PROVEN', f'http_{st}_log_{len(hits)}'
    if k == 'git_push':
        prior = ctx['prior']
        if prior.get('git_prep') != 'OK':
            return 'NOT_PROVEN', 'not_prepared'
        if f.get('absent'):
            return ('ABSENT', 'no_ssh_client') if f['via'] == 'ssh' else ('NOT_PROVEN', 'no_git')
        if f['rc'] == 0:
            return 'OPEN', 'git_exit_0'
        err = f['stderr_tail']
        if f['via'] == 'proxy':
            # R4 C-01: положительная привязка по времени. git получил ответ 403 от посредника (единственная
            # достижимая точка — стена клетки); посредник пишет решение по каждому соединению; в окне попытки git
            # (пока в сеансе идёт только git) запись аренды ровно одна — значит, она и есть запись git.
            # Запись вне окон своих попыток (NEW_NEGATIVE_6) — не объяснена, и вывод не доказан.
            # R5 C-01: владелец сокета каждой записи — сам сеанс (uid и cgroup называет ядро посреднику), адрес —
            # адрес сеанса; сеанс последователен, и в окне git в группе процессов сеанса идёт только git, поэтому
            # единственная запись в этом окне — соединение git. Её порт не равен порту ни одной другой попытки.
            # R6 C-01: окно и владелец уже не доказывают, что запись — от git (NEW_NEGATIVE_R6_N01: другой порт той
            # же группы процессов). git ходит к посреднику только через переходник сеанса; переходник знает точный
            # адрес и порт каждого своего соединения. Каждому соединению — ровно одна запись посредника с этим
            # адресом:портом, NOT_ALLOWED, github.com:443, в окне; других записей аренды в окне нет; ответ 403.
            mine = proxy_hits(ctx['proxy_log'], ctx['lease'])
            bad = owner_problem(ctx)
            if bad:
                return 'NOT_PROVEN', bad
            cs = relay_conns(f)
            if cs is None:
                return 'NOT_PROVEN', 'relay_report_incomplete'
            inw = [e for e in mine if in_window(e.get('ts'), window(a))]
            other = {str(x['facts'].get('lport')) for x in ctx['attempts'] if isinstance(x, dict)
                     and isinstance(x.get('facts'), dict) and x is not a and x['facts'].get('lport') is not None}
            peers = [f"{c['src']}:{c['lport']}" for c in cs]
            if len(set(peers)) != len(peers) or any(str(c['lport']) in other for c in cs):
                return 'NOT_PROVEN', 'relay_port_reused'
            for c, pr in zip(cs, peers):
                if c.get('target') != 'github.com:443' or c.get('status') != 403 or c.get('err') is not None:
                    return 'NOT_PROVEN', 'relay_not_403'
                hit = [e for e in inw if e.get('peer') == pr]
                if len(hit) != 1 or hit[0].get('decision') != 'NOT_ALLOWED' or hit[0].get('target') != 'github.com:443':
                    return 'NOT_PROVEN', f'relay_log_{len(hit)}'
            if len(inw) != len(cs) or any(e.get('decision') == 'ALLOWED' for e in mine):
                return 'NOT_PROVEN', f'proxy_unconfirmed_{len(inw)}'
            # R7 C-01: соединение переходника открыл именно git этой попытки, и git сам сообщил отказ SOCKS5
            # (NEW_NEGATIVE_R7_01-A: rc 128 без отказа SOCKS; -B: чужой клиент файла-сокета).
            cage = next(x['facts'] for x in ctx['attempts'] if isinstance(x, dict) and x.get('name') == 'cage')
            why = peer_problem(cs, f.get('git_pid'), cage.get('uid'))
            if why:
                return 'NOT_PROVEN', why
            if f['rc'] in (124, 127) or not isinstance(err, str) or not SOCKS_REFUSED.search(err):
                return 'NOT_PROVEN', 'git_no_socks_refusal'
            return 'DENIED_POLICY', 'proxy_403_NOT_ALLOWED'
        if f['via'] == 'direct':
            failed = {m.group(1) for m in CURL_FAIL.finditer(err)}
            tried = set(f['resolve'])
            # IPv6-адреса без IPv6 у самого хоста curl отбрасывает другим текстом — их отказ доказан попыткой tcp (ABSENT)
            need = {ip for ip in tried if fam(ip) == 'v4' or c['host_v6'] is not False}
            if CURL_CONNECTED.search(err) or not need or not need <= failed or not failed <= tried:
                return 'NOT_PROVEN', 'direct_unconfirmed'
            if all(prior.get(f'tcp_443_{ip_tag(ip)}') == 'DENIED_POLICY' for ip in need):
                return 'DENIED_POLICY', 'direct_refused_all'
            return 'NOT_PROVEN', 'tcp443_not_denied'
        if f['via'] == 'ssh':
            m = SSH_FAIL.search(err)
            if m and m.group(1) == f['ip'] and prior.get(f'tcp_22_{ip_tag(f["ip"])}') == 'DENIED_POLICY':
                return 'DENIED_POLICY', 'ssh_refused'
            return 'NOT_PROVEN', 'ssh_unconfirmed'
    return 'NOT_PROVEN', 'unknown_kind'


def judge(attempts, ctx):
    """Исходы всех попыток по порядку; prior — уже вычисленные исходы (git ссылается на tcp и git_prep)."""
    prior, out = {}, []
    start = ctx.get('start')
    bad = start_problem(start) or series_problem(attempts)
    bad = bad or time_problem(start, attempts)
    ctx = dict(ctx, attempts=attempts)
    rank = {'cage': 0, 'git_push': 2}
    order = sorted(range(len(attempts)), key=lambda i: rank.get(attempts[i].get('kind') if isinstance(attempts[i], dict) else None, 1))
    res = [None] * len(attempts)
    for i in order:
        a = attempts[i]
        why_bind = (bad if bad.startswith(('session_', 'duplicate_')) else 'start_' + bad.replace(' ', '_')) \
            if bad else binding_problem(a, start)
        if why_bind:                     # R2 C-01: попытка не своего назначения — исход не доказан
            oc, why = 'NOT_PROVEN', why_bind
        else:
            oc, why = classify(a, dict(ctx, prior=prior))
        prior[a.get('name') if isinstance(a, dict) else None] = oc
        res[i] = (oc, why)
    for a, (oc, why) in zip(attempts, res):
        out.append((a.get('name') if isinstance(a, dict) else None, oc, why))
    return out


def step_of(name):
    """Шаг карты для попытки: 3.5.5.1 — git push, 3.5.5.2 — API GitHub, 3.5.5 — общие условия обоих."""
    if name.startswith(('push_', 'git_prep', 'tcp_22_')):
        return '3.5.5.1'
    if name.startswith(('connect_', 'plain_get', 'tcp_443_')):
        return '3.5.5.2'
    return '3.5.5'


def cleanup_problem(c):
    """R3 M-03, R4 M-02: уборка подтверждена — экземпляр остановлен и замаскирован на эту загрузку, И в базе есть
    строка session_start этой аренды в конечном состоянии: её первичный ключ навсегда закрывает новый запуск
    (lease_reserve_start → ALREADY_STARTED), в том числе после перезагрузки, когда маски в /run уже нет.
    Строки нет (NONE) — «неизвестно», не SAFE."""
    if not isinstance(c, dict):
        return 'cleanup_missing'
    if c.get('status') != 'SAFE':
        return 'cleanup_' + str(c.get('status'))
    if c.get('unit_active_after') not in ('inactive', 'failed', 'unknown') or c.get('load_state') != 'masked' \
            or c.get('session_state') not in SEALED \
            or not isinstance(c.get('kept_copy'), str) or c['kept_copy'].startswith('failed_'):
        return 'cleanup_not_sealed'
    return None


def journal_chain(segments):
    """R4 M-04: segments — [(имя, байты)] по порядку имён 000001.jsonl, 000002.jsonl… (подряд, без пропусков).
    Сегмент пишется один раз (новый файл) и больше не меняется. Сегмент ЦЕЛЫЙ — все строки с переводом строки,
    первая — SERIES_START, последняя — SERIES_END со счётом записей. НЕДОПИСАННЫЙ (обрыв записи: нет последнего
    перевода строки или нет END) не правится и не удаляется: следующий сегмент продолжает цепочку от последнего
    целого и перечисляет недописанные в skipped_segments первой записи. Испорченная строка в середине (неверный JSON
    с переводом строки, разрыв цепочки сумм) — отказ всего журнала: так обрыв не выглядит.
    → (записи целых сегментов, имена недописанных, причина отказа или None, (seq, prev, недописанные после целого))."""
    out, broken, pending, seq, prev = [], [], [], 0, ZERO
    for i, (name, data) in enumerate(segments, 1):
        if name != '%06d.jsonl' % i:
            return out, broken, 'segment names are not contiguous', None
        lines = data.split(b'\n')
        tail = lines.pop()               # b'' — сегмент кончается переводом строки; иначе — оборванная строка
        s, p, recs = seq, prev, []
        for j, raw in enumerate(lines):
            try:
                rec = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                return out, broken, f'{name}: bad JSON at seq {s + 1}', None
            if not isinstance(rec, dict):
                return out, broken, f'{name}: bad JSON at seq {s + 1}', None
            if j == 0 and rec.get('skipped_segments') != pending:
                return out, broken, f'{name}: broken segments not declared', None
            if rec.get('seq') != s + 1 or rec.get('prev_sha256') != p:
                return out, broken, f'{name}: chain broken at seq {s + 1}', None
            s, p = rec['seq'], hashlib.sha256(raw).hexdigest()
            recs.append(rec)
        whole = tail == b'' and len(recs) >= 2 and recs[0].get('kind') == 'SERIES_START' \
            and recs[-1].get('kind') == 'SERIES_END' and recs[-1].get('records') == len(recs) - 1
        if whole:
            out += recs
            seq, prev, pending = s, p, []
        else:
            broken.append(name)
            pending = pending + [name]
    return out, broken, None, (seq, prev, pending)


def refs_parse(text):
    head, sep, body = text.partition('\n---\n')
    if not sep:
        raise ValueError('no separator')
    if head.splitlines()[0] != 'ZPROBE_REFS v2':
        raise ValueError('bad header')
    kv = dict(ln.split('=', 1) for ln in head.splitlines()[1:] if '=' in ln)
    refs = set()
    for ln in body.splitlines():
        if not ln.strip():
            continue
        m = re.fullmatch(r'([0-9a-f]{40})\t(refs/heads/zprobe/\S+)', ln)
        if not m:
            raise ValueError('bad ref line')
        refs.add(m.group(2))
    return kv, refs


def refs_problem(before, after, series, challenge, run_utc, tool_sha):
    """R5 M-01: снимки веток GitHub (компьютер оператора) против прогона. Время прогона run_utc берётся из записи
    START журнала (zprobe_verify.py --refs), а не из набранной строки. None — ветка пробы не появилась и набор веток
    не изменился за время прогона этой серии; иначе причина."""
    try:
        kb, rb = refs_parse(before)
        ka, ra = refs_parse(after)
    except (ValueError, IndexError, AttributeError) as e:
        return 'snapshot malformed: ' + str(e)
    for k, w in ((kb, 'before'), (ka, 'after')):
        if k.get('when') != w or k.get('repo') != REFS_REPO or k.get('prefix') != REFS_PREFIX:
            return f'{w} snapshot is not for this repository or prefix'
        if k.get('series') != series:
            return f'{w} snapshot is for another series'
        if k.get('tool_sha256') != tool_sha:
            return f'{w} snapshot made by a program not in pins'
        if k.get('rc') != '0':
            return f'{w} snapshot read failed rc={k.get("rc")}'
        if not ISO.match(k.get('time_utc', '')):
            return f'{w} snapshot time malformed'
    if not (isinstance(run_utc, list) and len(run_utc) == 2 and all(isinstance(x, str) and ISO.match(x)
                                                                     for x in run_utc) and run_utc[0] <= run_utc[1]):
        return 'run times malformed'
    tb, ta = iso_us(kb['time_utc']), iso_us(ka['time_utc'])
    t0, t1 = iso_us(run_utc[0]), iso_us(run_utc[1])
    if not tb < t0 or not t1 < ta:
        return 'snapshots do not bracket the run (before < start, end < after)'
    if t0 - tb > REFS_GAP * 1_000_000 or ta - t1 > REFS_GAP * 1_000_000:
        return 'snapshot too far from the run'
    if 'refs/heads/zprobe/pb1-' + challenge[:8] in ra:
        return 'probe branch exists on GitHub'
    if ra != rb:
        return 'zprobe refs changed during the series'
    return None


def segments_digest(segments):
    """Якорь телефона: число сегментов и SHA-256 над «имя, SHA-256 содержимого» каждого. Сегменты не меняются."""
    h = hashlib.sha256()
    for name, data in segments:
        h.update(f'{name} {hashlib.sha256(data).hexdigest()}\n'.encode('ascii'))
    return len(segments), h.hexdigest()
