#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_gitlink.py
# ВЕРСИЯ: v0.3  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-19 12:33 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 16:10 +02:00
# v0.3 (REL156 L-355-REL156-01): только текст — окно в мкс по часам journald (__REALTIME_TIMESTAMP), не «монотонных».
# ИСПОЛНИТЕЛЬ: Claude (терминал zavod, пускатель)
# НАЗНАЧЕНИЕ: B15, связь записей стены с сокетами git попыток push_https_direct и push_ssh (DECISION_B15_PUSH_AND_START
#   часть A) и проверка пробы push_proxy_equiv. Чистые функции, без чтения /proc: разбор /proc/net/tcp{,6} (С1), строк
#   libcurl «connect to … from … port N failed» (С2), link_verdict() и proxy_equiv_verdict() по правилу fail-closed.
#   Запасных путей «по единственности» нет (REL152 M-355-REL152-01).
# v0.2 (аудит REL154): ветка переходника (relay) убрана — переходник невозможен (REL153); M-355-REL154-03 — git должен
#   завершиться с целым ненулевым кодом (rc=None, строка, bool — NOT_PROVEN), опрос сокетов С1 — без ошибок и
#   остановлен; M-355-REL154-01 — proxy_equiv_verdict: точные байты CONNECT git <версия>, настройка посредника, ответ
#   403 целиком, ровно одна запись посредника в окне с портом, uid и cgroup сокета сеанса, NOT_ALLOWED. Итог пробы —
#   не git push (фраза 3.5.5.1 в редакции аудитора REL154 п. 2, подпись оператора).
import ipaddress
import re

TCP_STATES = {1: 'ESTABLISHED', 2: 'SYN_SENT', 3: 'SYN_RECV', 4: 'FIN_WAIT1', 5: 'FIN_WAIT2', 6: 'TIME_WAIT',
              7: 'CLOSE', 8: 'CLOSE_WAIT', 9: 'LAST_ACK', 10: 'LISTEN', 11: 'CLOSING', 12: 'NEW_SYN_RECV'}
PROXY_ADDR = '127.0.0.2'
PROXY_PORT = 3128
UNBOUND = ('0.0.0.0', '::')
_C2 = re.compile(r'connect to (\S+) port (\d+) from (\S+) port (\d+) failed')


def _hex_addr(h):
    """Адрес из /proc/net/tcp: IPv4 — 8 знаков, IPv6 — 32 знака; каждое 32-битное слово в порядке байтов хоста (x86 —
    младший байт первым)."""
    if len(h) == 8:
        return str(ipaddress.IPv4Address(bytes.fromhex(h)[::-1]))
    if len(h) == 32:
        b = b''.join(bytes.fromhex(h[i:i + 8])[::-1] for i in range(0, 32, 8))
        return str(ipaddress.IPv6Address(b))
    raise ValueError('bad_addr')


def parse_net_tcp(text):
    """Текст /proc/net/tcp или tcp6 → {inode: {'quad': (свой адрес, свой порт, адрес цели, порт цели), 'state': имя}}.
    Строки с inode 0 (TIME_WAIT без владельца) пропускаются: владельца у них нет, связь по ним невозможна."""
    out = {}
    for line in text.splitlines()[1:]:
        p = line.split()
        if len(p) < 10:
            continue
        try:
            la, lp = p[1].split(':')
            ra, rp = p[2].split(':')
            inode = int(p[9])
            if inode == 0:
                continue
            out[inode] = {'quad': (_hex_addr(la), int(lp, 16), _hex_addr(ra), int(rp, 16)),
                          'state': TCP_STATES.get(int(p[3], 16), 'UNKNOWN')}
        except (ValueError, IndexError):
            continue
    return out


def socket_inodes(fd_links):
    """Ссылки /proc/<pid>/fd/* → множество inode сокетов («socket:[12345]»)."""
    out = set()
    for x in fd_links:
        m = re.fullmatch(r'socket:\[(\d+)\]', x or '')
        if m:
            out.add(int(m.group(1)))
    return out


def parse_c2(stderr):
    """Строки libcurl из GIT_TRACE_CURL → список четвёрок (свой адрес, свой порт, адрес цели, порт цели).
    Свой адрес 0.0.0.0 или :: — четвёрка неполна и в связь не идёт (проверка на ПК 2026-11-19 12:27: Windows так и пишет)."""
    out = []
    for m in _C2.finditer(stderr or ''):
        dst, dport, src, sport = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        try:
            src, dst = str(ipaddress.ip_address(src)), str(ipaddress.ip_address(dst))
        except ValueError:
            continue
        if src in UNBOUND:
            continue
        out.append((src, sport, dst, dport))
    return out


def _in(ts, w):
    return isinstance(ts, int) and w is not None and w[0] <= ts <= w[1]


def link_verdict(att):
    """Только push_https_direct и push_ssh. att: {'rc' (целый код выхода), 'exited' (True — процесс git завершён),
    'watch': {'polls', 'errors', 'stopped'} (опрос С1), 'window': (от, до) мкс по часам journald (__REALTIME_TIMESTAMP, как ts строк), 'boot_id',
    'sockets': [{pid, start, comm, quad, states}] (С1), 'stderr' (полный, С2), 'klog': [{src, spt, dst, dpt, ts, boot}]
    (С3, ВСЕ строки серии), 'proxy': [{peer, ts, …}] (записи посредника серии)}. → (исход, причина)."""
    try:
        return _verdict(att)
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as e:
        return 'NOT_PROVEN', 'bad_facts_' + type(e).__name__


def _window_ok(w):
    return isinstance(w, (tuple, list)) and len(w) == 2 and all(type(x) is int for x in w) and w[0] < w[1]


def _verdict(a):
    w, boot = a['window'], a['boot_id']
    if not _window_ok(w):
        return 'NOT_PROVEN', 'bad_window'
    if not isinstance(boot, str) or not boot:
        return 'NOT_PROVEN', 'no_boot_id'
    if a.get('exited') is not True:
        return 'NOT_PROVEN', 'git_not_ended'
    rc = a['rc']
    if type(rc) is not int:
        return 'NOT_PROVEN', 'git_rc_not_int'
    if rc == 0:
        return 'NOT_PROVEN', 'git_rc_0'
    wt = a['watch']
    if not (isinstance(wt, dict) and wt.get('stopped') is True and type(wt.get('polls')) is int and wt['polls'] > 0
            and type(wt.get('errors')) is int and wt['errors'] == 0):
        return 'NOT_PROVEN', 'socket_watch_incomplete'
    socks = a['sockets']
    for s in socks:
        if not (type(s.get('pid')) is int and type(s.get('start')) is int):
            return 'NOT_PROVEN', 'socket_without_pid_start'
        if s['quad'][2] == PROXY_ADDR:
            return 'NOT_PROVEN', 'direct_used_proxy'
        if 'ESTABLISHED' in s['states']:
            return 'NOT_PROVEN', 'established_outside'
    if any(_in(x.get('ts'), w) for x in a['proxy']):
        return 'NOT_PROVEN', 'proxy_record_in_window'
    git_q = {tuple(s['quad']) for s in socks} | set(parse_c2(a['stderr']))
    klog = a['klog']
    in_w = [x for x in klog if _in(x.get('ts'), w)]
    for x in in_w:
        if x.get('boot') != boot:
            return 'NOT_PROVEN', 'kernel_other_boot'
        if (x['src'], x['spt'], x['dst'], x['dpt']) not in git_q:
            return 'NOT_PROVEN', 'kernel_line_unlinked'
    for x in klog:
        if not _in(x.get('ts'), w) and (x['src'], x['spt'], x['dst'], x['dpt']) in git_q:
            return 'NOT_PROVEN', 'git_quad_outside_window'
    seen = {(x['src'], x['spt'], x['dst'], x['dpt']) for x in in_w}
    for q in git_q:
        if q not in seen:
            return 'NOT_PROVEN', 'git_socket_without_kernel_line'
    if not in_w:
        return 'NOT_PROVEN', 'no_refusal_record'
    return 'DENIED_POLICY', 'linked_kernel'


PROXY_URL = 'http://127.0.0.2:3128'
REMOTE_PREFIX = 'https://github.com/'
TARGET = 'github.com:443'
_VER = re.compile(r'\A\d+\.\d+\.\d+\Z')


def connect_bytes(git_version):
    """Байты, которые git <версия> шлёт посреднику при push по https через http-посредника (сняты с git 2.43 в
    CI-лаборатории и на ПК, REL154 D1). Неизвестный вид версии — None."""
    if not isinstance(git_version, str) or not _VER.match(git_version):
        return None
    return (f'CONNECT {TARGET} HTTP/1.1\r\nHost: {TARGET}\r\nUser-Agent: git/{git_version}\r\n'
            'Proxy-Connection: Keep-Alive\r\n\r\n').encode('ascii')


def proxy_equiv_verdict(f):
    """push_proxy_equiv: сеанс сам шлёт посреднику те же байты, что git push. f: {'git_version' (git --version той же
    серии), 'git_proxy' (http.proxy попыток push), 'remote' (адрес удалённого хранилища), 'sent' (bytes), 'own':
    {'src', 'port', 'peer': (адрес, порт)} (getsockname/getpeername сокета сеанса), 'reply': {'complete', 'status',
    'error'}, 'cage': {'uid', 'cgroup_id'}, 'window', 'proxy': [{peer, uid, cgroup, target, decision, ts}] (ВСЕ записи
    посредника серии), 'other_ports': [порты других попыток]}. → (исход, причина). Итог — не git push."""
    try:
        return _equiv(f)
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as e:
        return 'NOT_PROVEN', 'bad_facts_' + type(e).__name__


def _equiv(f):
    w = f['window']
    if not _window_ok(w):
        return 'NOT_PROVEN', 'bad_window'
    want = connect_bytes(f['git_version'])
    if want is None:
        return 'NOT_PROVEN', 'git_version_unknown'
    if f['git_proxy'] != PROXY_URL or not isinstance(f['remote'], str) or not f['remote'].startswith(REMOTE_PREFIX):
        return 'NOT_PROVEN', 'settings_differ'
    if type(f['sent']) is not bytes or f['sent'] != want:
        return 'NOT_PROVEN', 'bytes_differ'
    own = f['own']
    if tuple(own['peer']) != (PROXY_ADDR, PROXY_PORT) or type(own['port']) is not int or not isinstance(own['src'], str):
        return 'NOT_PROVEN', 'own_socket_bad'
    if own['port'] in set(f['other_ports']):
        return 'NOT_PROVEN', 'own_port_reused'
    r = f['reply']
    if r.get('complete') is not True or r.get('error') is not None or type(r.get('status')) is not int:
        return 'NOT_PROVEN', 'reply_incomplete'
    if r['status'] != 403:
        return 'NOT_PROVEN', 'reply_not_403'
    cage = f['cage']
    if type(cage.get('uid')) is not int or type(cage.get('cgroup_id')) is not int:
        return 'NOT_PROVEN', 'owner_unknown'
    if any(x.get('decision') == 'ALLOWED' for x in f['proxy']):
        return 'NOT_PROVEN', 'proxy_allowed_somewhere'
    inw = [x for x in f['proxy'] if _in(x.get('ts'), w)]
    if len(inw) != 1:
        return 'NOT_PROVEN', f'proxy_records_in_window_{len(inw)}'
    x = inw[0]
    if x.get('peer') != f"{own['src']}:{own['port']}":
        return 'NOT_PROVEN', 'proxy_record_other_port'
    if x.get('uid') != cage['uid'] or x.get('cgroup') != cage['cgroup_id']:
        return 'NOT_PROVEN', 'proxy_record_foreign_owner'
    if x.get('target') != TARGET or x.get('decision') != 'NOT_ALLOWED':
        return 'NOT_PROVEN', 'proxy_record_not_refusal'
    return 'DENIED_POLICY', 'equiv_connect_403_NOT_ALLOWED'
