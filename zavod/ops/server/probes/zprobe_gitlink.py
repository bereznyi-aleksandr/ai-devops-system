#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_gitlink.py
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-19 12:33 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 12:33 +02:00
# ИСПОЛНИТЕЛЬ: Claude (терминал zavod, пускатель)
# НАЗНАЧЕНИЕ: B15, связь записей стены с сокетами git попытки push_* (проект DECISION_B15_PUSH_AND_START v0.3 часть A,
#   на аудите REL153; офлайн-код разрешён REL152). Чистые функции, без чтения /proc: разбор /proc/net/tcp{,6} (С1),
#   строк libcurl «connect to … from … port N failed» (С2) и решение link_verdict() по правилу fail-closed: DENIED_POLICY
#   только если каждая строка ядра и каждая запись посредника в окне связаны полной четвёркой с сокетом git; иначе
#   NOT_PROVEN. Запасных путей «по единственности» нет (REL152 M-355-REL152-01).
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
    """att: {'rc', 'window': (от, до) мкс монотонных, 'boot_id', 'sockets': [{pid, start, comm, quad, states}] (С1),
    'stderr' (полный, С2), 'klog': [{src, spt, dst, dpt, ts, boot}] (С3, ВСЕ строки серии), 'proxy': [{peer_port,
    target, outcome, ts}] (записи посредника серии), 'relay': [{git_quad, own_quad, found}] (переходник для proxy)}.
    → (исход, причина)."""
    try:
        return _verdict(att)
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        return 'NOT_PROVEN', 'bad_facts_' + type(e).__name__


def _verdict(a):
    w, boot = a['window'], a['boot_id']
    if not (isinstance(w, (tuple, list)) and len(w) == 2 and all(isinstance(x, int) for x in w) and w[0] < w[1]):
        return 'NOT_PROVEN', 'bad_window'
    if not isinstance(boot, str) or not boot:
        return 'NOT_PROVEN', 'no_boot_id'
    if a['rc'] == 0:
        return 'NOT_PROVEN', 'git_rc_0'
    socks = a['sockets']
    for s in socks:
        if not (isinstance(s.get('pid'), int) and isinstance(s.get('start'), int)):
            return 'NOT_PROVEN', 'socket_without_pid_start'
        if 'ESTABLISHED' in s['states'] and s['quad'][2] != PROXY_ADDR:
            return 'NOT_PROVEN', 'established_outside'
    git_q = {tuple(s['quad']) for s in socks if s['quad'][2] != PROXY_ADDR} | set(parse_c2(a['stderr']))
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
    relay = a.get('relay') or []
    if any(r.get('found') is not True for r in relay):
        return 'NOT_PROVEN', 'relay_git_socket_not_found'
    own_ports = {}
    for r in relay:
        if r['git_quad'][2] != PROXY_ADDR or r['own_quad'][2] != PROXY_ADDR or r['own_quad'][3] != PROXY_PORT:
            return 'NOT_PROVEN', 'relay_bad_quad'
        if r['own_quad'][1] in own_ports:
            return 'NOT_PROVEN', 'relay_port_conflict'
        own_ports[r['own_quad'][1]] = r
    git_relay = {tuple(s['quad']) for s in socks if s['quad'][2] == PROXY_ADDR}
    for r in relay:
        if tuple(r['git_quad']) not in git_relay:
            return 'NOT_PROVEN', 'relay_quad_not_git_socket'
    pr = [x for x in a['proxy'] if _in(x.get('ts'), w)]
    for x in pr:
        if x.get('peer_port') not in own_ports:
            return 'NOT_PROVEN', 'proxy_record_unlinked'
        if x.get('target') != 'github.com:443' or x.get('outcome') != 'NOT_ALLOWED':
            return 'NOT_PROVEN', 'proxy_record_not_refusal'
    if len({x['peer_port'] for x in pr}) != len(pr):
        return 'NOT_PROVEN', 'proxy_two_records_one_port'
    for p in own_ports:
        if p not in {x['peer_port'] for x in pr}:
            return 'NOT_PROVEN', 'relay_without_proxy_record'
    if not in_w and not pr:
        return 'NOT_PROVEN', 'no_refusal_record'
    return 'DENIED_POLICY', 'linked_' + ('proxy' if pr else 'kernel')
