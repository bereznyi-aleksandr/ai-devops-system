#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_gitlink.py
# ВЕРСИЯ: v0.2  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-19 12:33 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 13:05 +02:00
# v0.2 (REL154): без переходника; строгий код выхода и завершение git, полный опрос С1 (M-154-03); проба
#   push_proxy_equiv — точные байты, настройки, 403, одна своя запись посредника, отрицательный набор (M-154-01, L-02).
# ИСПОЛНИТЕЛЬ: Claude (терминал zavod, пускатель)
# НАЗНАЧЕНИЕ: офлайн-тесты zprobe_gitlink.py (DECISION_B15 v0.3 часть A): разбор /proc/net/tcp{,6}, строк libcurl,
#   положительные случаи по видам push_* и отрицательные из v0.3 (строка ядра без пары, другой BOOT_ID, пара вне окна,
#   С2 с 0.0.0.0, запись посредника без пары, переходник не нашёл сокет, ESTABLISHED наружу, git rc 0, журнал без С1).
import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zprobe_gitlink as G  # noqa: E402

OK, BAD = [], []


def case(name, got, want):
    good = got[0] == want if isinstance(want, str) else got == want
    (OK if good else BAD).append(name)
    print(('PASS ' if good else 'FAIL ') + f'{name} -> {got}', flush=True)


# 1. Разбор /proc/net/tcp и tcp6
NET4 = ('  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n'
        '   0: 0500000A:9C40 0379528C:01BB 02 00000000:00000000 01:00000064 00000002 61234        0 123456 2 0 100 0 0 10 -1\n'
        '   1: 0200007F:C738 0200007F:0C38 01 00000000:00000000 00:00000000 00000000 61234        0 123457 1 0 20 4 30 10 -1\n'
        '   2: 0500000A:9C41 0379528C:01BB 06 00000000:00000000 03:00001770 00000000     0        0 0 3 0\n')
n4 = G.parse_net_tcp(NET4)
case('G01 tcp4 SYN_SENT quad', (n4[123456]['quad'], n4[123456]['state']),
     (('10.0.0.5', 40000, '140.82.121.3', 443), 'SYN_SENT'))
case('G02 tcp4 loopback ESTABLISHED to proxy', (n4[123457]['quad'], n4[123457]['state']),
     (('127.0.0.2', 51000, '127.0.0.2', 3128), 'ESTABLISHED'))
case('G03 TIME_WAIT without owner (inode 0) skipped', (0 in n4, len(n4)), (False, 2))
NET6 = ('  sl  local_address                         remote_address                        st tx_queue rx_queue tr tm->when '
        'retrnsmt   uid  timeout inode\n'
        '   0: 00000000000000000000000001000000:9C42 C0500626000000800000000054010000:0016 02 00000000:00000000 01:00000064 '
        '00000002 61234 0 223344 2 0 100 0 0 10 -1\n')
n6 = G.parse_net_tcp(NET6)
case('G04 tcp6 quad', n6[223344]['quad'], ('::1', 40002, '2606:50c0:8000::154', 22))
case('G05 fd links -> socket inodes', G.socket_inodes(['socket:[123456]', 'pipe:[9]', '/dev/null', 'socket:[x]', None]),
     {123456})
# 2. Строки libcurl
ERR = ('== Info:   Trying 140.82.121.3:443...\n'
       '== Info: connect to 140.82.121.3 port 443 from 10.0.0.5 port 40000 failed: Connection timed out\n'
       '== Info: connect to 140.82.121.4 port 443 from 0.0.0.0 port 60124 failed: Timed out\n')
case('G06 C2 full quad parsed, 0.0.0.0 dropped', G.parse_c2(ERR), [('10.0.0.5', 40000, '140.82.121.3', 443)])


# 3. Решение: push_https_direct и push_ssh (v0.2: rc целый ненулевой, git завершён, опрос С1 полный)
W = (1000, 200000)
Q4 = ('10.0.0.5', 40000, '140.82.121.3', 443)
WATCH = {'polls': 900, 'errors': 0, 'stopped': True}


def kl(q, ts, boot='B'):
    return {'src': q[0], 'spt': q[1], 'dst': q[2], 'dpt': q[3], 'ts': ts, 'boot': boot}


DIRECT = {'rc': 128, 'exited': True, 'watch': dict(WATCH), 'window': W, 'boot_id': 'B', 'stderr': '',
          'sockets': [{'pid': 700, 'start': 9001, 'comm': 'git-remote-http', 'quad': Q4, 'states': ['SYN_SENT']}],
          'klog': [kl(Q4, 1500 + i * 1000) for i in range(7)], 'proxy': []}
case('G07 direct: every kernel line linked -> DENIED_POLICY', G.link_verdict(DIRECT), ('DENIED_POLICY', 'linked_kernel'))
d = copy.deepcopy(DIRECT)
d['sockets'] = []
d['stderr'] = ERR
case('G08 direct linked by C2 full quad only', G.link_verdict(d), ('DENIED_POLICY', 'linked_kernel'))
QS = ('10.0.0.5', 40100, '140.82.121.3', 22)
SSH = {'rc': 255, 'exited': True, 'watch': dict(WATCH), 'window': W, 'boot_id': 'B',
       'stderr': 'ssh: connect to host 140.82.121.3 port 22: Connection timed out',
       'sockets': [{'pid': 710, 'start': 9002, 'comm': 'ssh', 'quad': QS, 'states': ['SYN_SENT']}],
       'klog': [kl(QS, 2000), kl(QS, 3000), kl(QS, 5000)], 'proxy': []}
case('G09 ssh: linked by C1 quad', G.link_verdict(SSH), ('DENIED_POLICY', 'linked_kernel'))
case('G10 timeout kill rc 124 (int, process ended) -> DENIED_POLICY', G.link_verdict(dict(DIRECT, rc=124)),
     ('DENIED_POLICY', 'linked_kernel'))

# Отрицательные: связь
d = copy.deepcopy(DIRECT)
d['klog'].append(kl(('10.0.0.5', 40777, '140.82.121.3', 443), 9000))
case('G11 kernel line without git pair -> NOT_PROVEN', G.link_verdict(d), ('NOT_PROVEN', 'kernel_line_unlinked'))
d = copy.deepcopy(DIRECT)
d['klog'][3]['boot'] = 'OTHER'
case('G12 kernel line of another boot -> NOT_PROVEN', G.link_verdict(d), ('NOT_PROVEN', 'kernel_other_boot'))
d = copy.deepcopy(DIRECT)
d['klog'].append(kl(Q4, 500))
case('G13 git quad seen before window -> NOT_PROVEN', G.link_verdict(d), ('NOT_PROVEN', 'git_quad_outside_window'))
d = copy.deepcopy(DIRECT)
d['sockets'] = []
d['stderr'] = ERR.replace('from 10.0.0.5', 'from 0.0.0.0')
case('G14 C2 with 0.0.0.0 only -> NOT_PROVEN', G.link_verdict(d), ('NOT_PROVEN', 'kernel_line_unlinked'))
d = copy.deepcopy(DIRECT)
d['sockets'][0]['states'] = ['SYN_SENT', 'ESTABLISHED']
case('G15 git socket ESTABLISHED outside -> NOT_PROVEN', G.link_verdict(d), ('NOT_PROVEN', 'established_outside'))
d = copy.deepcopy(DIRECT)
d['klog'] = []
case('G17 git socket without kernel line -> NOT_PROVEN', G.link_verdict(d),
     ('NOT_PROVEN', 'git_socket_without_kernel_line'))
d = copy.deepcopy(DIRECT)
d['sockets'][0]['start'] = None
case('G18 socket without starttime (pid reuse unknown) -> NOT_PROVEN', G.link_verdict(d),
     ('NOT_PROVEN', 'socket_without_pid_start'))
d = copy.deepcopy(DIRECT)
d['sockets'].append({'pid': 700, 'start': 9001, 'comm': 'git-remote-http',
                     'quad': ('127.0.0.2', 51000, '127.0.0.2', 3128), 'states': ['ESTABLISHED']})
case('G19 direct attempt talked to proxy -> NOT_PROVEN', G.link_verdict(d), ('NOT_PROVEN', 'direct_used_proxy'))
d = copy.deepcopy(DIRECT)
d['proxy'] = [{'peer': '127.0.0.2:52000', 'ts': 4000}]
case('G20 proxy record inside direct window -> NOT_PROVEN', G.link_verdict(d), ('NOT_PROVEN', 'proxy_record_in_window'))
d = copy.deepcopy(SSH)
d['sockets'] = []
case('G25 ssh unique quad without C1 -> NOT_PROVEN (no uniqueness rule)', G.link_verdict(d),
     ('NOT_PROVEN', 'kernel_line_unlinked'))
P4 = dict(DIRECT, rc=124, stderr='', sockets=[], klog=[kl(Q4, 2000), kl(Q4, 3000)])
case('G27 pb1trial4-like facts -> NOT_PROVEN', G.link_verdict(P4), 'NOT_PROVEN')
d = copy.deepcopy(DIRECT)
d['sockets'], d['klog'] = [], []
case('G28 no records at all -> NOT_PROVEN', G.link_verdict(d), ('NOT_PROVEN', 'no_refusal_record'))
case('G29 bad window -> NOT_PROVEN', G.link_verdict(dict(DIRECT, window=(5, 5))), ('NOT_PROVEN', 'bad_window'))
case('G30 missing field -> NOT_PROVEN', G.link_verdict({'rc': 1}), 'NOT_PROVEN')

# M-355-REL154-03: код выхода и завершение процесса
for label, rc, why in (('0', 0, 'git_rc_0'), ('None', None, 'git_rc_not_int'), ("'unknown'", 'unknown', 'git_rc_not_int'),
                       ("'128'", '128', 'git_rc_not_int'), ('True', True, 'git_rc_not_int'), ('128.0', 128.0, 'git_rc_not_int')):
    case(f'G31 rc={label} -> NOT_PROVEN', G.link_verdict(dict(DIRECT, rc=rc)), ('NOT_PROVEN', why))
for label, ex in (('False', False), ('None', None), ("'yes'", 'yes')):
    case(f'G32 exited={label} -> NOT_PROVEN', G.link_verdict(dict(DIRECT, exited=ex)), ('NOT_PROVEN', 'git_not_ended'))
d = copy.deepcopy(DIRECT)
del d['exited']
case('G32 exited missing -> NOT_PROVEN', G.link_verdict(d), ('NOT_PROVEN', 'git_not_ended'))
for label, wt in (('errors 1', dict(WATCH, errors=1)), ('not stopped', dict(WATCH, stopped=False)),
                  ('0 polls', dict(WATCH, polls=0)), ('errors None', dict(WATCH, errors=None)), ('None', None)):
    case(f'G33 socket watch {label} -> NOT_PROVEN', G.link_verdict(dict(DIRECT, watch=wt)),
         ('NOT_PROVEN', 'socket_watch_incomplete'))

# 4. push_proxy_equiv (M-355-REL154-01, L-355-REL154-02)
V = '2.43.0'
SENT = (b'CONNECT github.com:443 HTTP/1.1\r\nHost: github.com:443\r\nUser-Agent: git/2.43.0\r\n'
        b'Proxy-Connection: Keep-Alive\r\n\r\n')
EQ = {'git_version': V, 'git_proxy': 'http://127.0.0.2:3128', 'remote': 'https://github.com/zavod/probe.git',
      'sent': SENT, 'own': {'src': '127.0.0.2', 'port': 52000, 'peer': ('127.0.0.2', 3128)},
      'reply': {'complete': True, 'status': 403, 'error': None}, 'cage': {'uid': 61234, 'cgroup_id': 777},
      'window': W, 'other_ports': [51000, 51001],
      'proxy': [{'peer': '127.0.0.2:52000', 'uid': 61234, 'cgroup': 777, 'target': 'github.com:443',
                 'decision': 'NOT_ALLOWED', 'ts': 4000}]}
case('E01 equivalent CONNECT, 403, one own record -> DENIED_POLICY (not git push)', G.proxy_equiv_verdict(EQ),
     ('DENIED_POLICY', 'equiv_connect_403_NOT_ALLOWED'))
case('E02 template equals bytes captured from git 2.43 (D1)', (G.connect_bytes(V) == SENT, ''), (True, ''))
BYTES_BAD = (
    ('other git version in User-Agent', SENT.replace(b'git/2.43.0', b'git/2.44.0')),
    ('no Proxy-Connection header', SENT.replace(b'Proxy-Connection: Keep-Alive\r\n', b'')),
    ('extra header', SENT.replace(b'\r\n\r\n', b'\r\nX-Extra: 1\r\n\r\n')),
    ('LF instead of CRLF', SENT.replace(b'\r\n', b'\n')),
    ('Host differs', SENT.replace(b'Host: github.com:443', b'Host: github.com')),
    ('lowercase method', SENT.replace(b'CONNECT', b'connect')),
    ('HTTP/1.0', SENT.replace(b'HTTP/1.1', b'HTTP/1.0')),
    ('other target', SENT.replace(b'github.com:443', b'gitlab.com:443')),
    ('headers reordered', b'CONNECT github.com:443 HTTP/1.1\r\nUser-Agent: git/2.43.0\r\nHost: github.com:443\r\n'
                          b'Proxy-Connection: Keep-Alive\r\n\r\n'),
    ('trailing byte', SENT + b'x'),
    ('str instead of bytes', SENT.decode()),
)
for label, b in BYTES_BAD:
    case(f'E03 bytes: {label} -> NOT_PROVEN', G.proxy_equiv_verdict(dict(EQ, sent=b)), ('NOT_PROVEN', 'bytes_differ'))
for label, v in (('2.43', '2.43'), ('None', None), ('2.43.0.windows.1', '2.43.0.windows.1')):
    case(f'E04 git version {label} -> NOT_PROVEN', G.proxy_equiv_verdict(dict(EQ, git_version=v)),
         ('NOT_PROVEN', 'git_version_unknown'))
for label, k, v in (('proxy url other', 'git_proxy', 'http://127.0.0.1:3128'), ('proxy https', 'git_proxy',
                    'https://127.0.0.2:3128'), ('remote not github', 'remote', 'https://gitlab.com/x.git'),
                    ('remote ssh', 'remote', 'git@github.com:zavod/probe.git')):
    case(f'E05 settings: {label} -> NOT_PROVEN', G.proxy_equiv_verdict(dict(EQ, **{k: v})),
         ('NOT_PROVEN', 'settings_differ'))
for label, r, why in (('200', {'complete': True, 'status': 200, 'error': None}, 'reply_not_403'),
                      ('407', {'complete': True, 'status': 407, 'error': None}, 'reply_not_403'),
                      ('incomplete', {'complete': False, 'status': 403, 'error': None}, 'reply_incomplete'),
                      ('error', {'complete': True, 'status': 403, 'error': 'timeout'}, 'reply_incomplete'),
                      ('status str', {'complete': True, 'status': '403', 'error': None}, 'reply_incomplete')):
    case(f'E06 reply {label} -> NOT_PROVEN', G.proxy_equiv_verdict(dict(EQ, reply=r)), ('NOT_PROVEN', why))


def eqp(**chg):
    d = copy.deepcopy(EQ)
    d['proxy'][0].update(chg)
    return d


case('E07 record of another port -> NOT_PROVEN', G.proxy_equiv_verdict(eqp(peer='127.0.0.2:52001')),
     ('NOT_PROVEN', 'proxy_record_other_port'))
case('E08 record foreign uid -> NOT_PROVEN', G.proxy_equiv_verdict(eqp(uid=0)), ('NOT_PROVEN', 'proxy_record_foreign_owner'))
case('E09 record foreign cgroup -> NOT_PROVEN', G.proxy_equiv_verdict(eqp(cgroup=778)),
     ('NOT_PROVEN', 'proxy_record_foreign_owner'))
case('E10 record other target -> NOT_PROVEN', G.proxy_equiv_verdict(eqp(target='github.com:22')),
     ('NOT_PROVEN', 'proxy_record_not_refusal'))
case('E11 record ALLOWED -> NOT_PROVEN', G.proxy_equiv_verdict(eqp(decision='ALLOWED')),
     ('NOT_PROVEN', 'proxy_allowed_somewhere'))
case('E12 record outside window -> NOT_PROVEN', G.proxy_equiv_verdict(eqp(ts=300000)),
     ('NOT_PROVEN', 'proxy_records_in_window_0'))
d = copy.deepcopy(EQ)
d['proxy'].append(dict(d['proxy'][0], peer='127.0.0.2:52002', ts=5000))
case('E13 two records in window -> NOT_PROVEN', G.proxy_equiv_verdict(d), ('NOT_PROVEN', 'proxy_records_in_window_2'))
d = copy.deepcopy(EQ)
d['proxy'].append(dict(d['proxy'][0], decision='ALLOWED', ts=300000))
case('E14 ALLOWED anywhere in series -> NOT_PROVEN', G.proxy_equiv_verdict(d), ('NOT_PROVEN', 'proxy_allowed_somewhere'))
case('E15 own port used by another attempt -> NOT_PROVEN', G.proxy_equiv_verdict(dict(EQ, other_ports=[52000])),
     ('NOT_PROVEN', 'own_port_reused'))
d = copy.deepcopy(EQ)
d['own']['peer'] = ('127.0.0.1', 3128)
case('E16 own socket not to proxy -> NOT_PROVEN', G.proxy_equiv_verdict(d), ('NOT_PROVEN', 'own_socket_bad'))
case('E17 owner unknown -> NOT_PROVEN', G.proxy_equiv_verdict(dict(EQ, cage={'uid': None, 'cgroup_id': 777})),
     ('NOT_PROVEN', 'owner_unknown'))
case('E18 no records -> NOT_PROVEN', G.proxy_equiv_verdict(dict(EQ, proxy=[])), ('NOT_PROVEN', 'proxy_records_in_window_0'))
case('E19 missing field -> NOT_PROVEN', G.proxy_equiv_verdict({'window': W}), 'NOT_PROVEN')
case('E20 bad window -> NOT_PROVEN', G.proxy_equiv_verdict(dict(EQ, window=(9, 1))), ('NOT_PROVEN', 'bad_window'))

print(f'ZPROBE_GITLINK_TESTS {len(OK)}/{len(OK) + len(BAD)} ' + ('PASS' if not BAD else 'FAIL'))
sys.exit(1 if BAD else 0)
