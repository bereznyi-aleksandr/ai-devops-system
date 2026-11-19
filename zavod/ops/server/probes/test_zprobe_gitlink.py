#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_gitlink.py
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-19 12:33 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 12:33 +02:00
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

# 3. Решение
W = (1000, 200000)
Q4 = ('10.0.0.5', 40000, '140.82.121.3', 443)


def kl(q, ts, boot='B'):
    return {'src': q[0], 'spt': q[1], 'dst': q[2], 'dpt': q[3], 'ts': ts, 'boot': boot}


DIRECT = {'rc': 128, 'window': W, 'boot_id': 'B', 'stderr': '',
          'sockets': [{'pid': 700, 'start': 9001, 'comm': 'git-remote-http', 'quad': Q4, 'states': ['SYN_SENT']}],
          'klog': [kl(Q4, 1500 + i * 1000) for i in range(7)], 'proxy': [], 'relay': []}
case('G07 direct: every kernel line linked -> DENIED_POLICY', G.link_verdict(DIRECT), ('DENIED_POLICY', 'linked_kernel'))
d = copy.deepcopy(DIRECT)
d['sockets'] = []
d['stderr'] = ERR
case('G08 direct linked by C2 full quad only', G.link_verdict(d), ('DENIED_POLICY', 'linked_kernel'))
QS = ('10.0.0.5', 40100, '140.82.121.3', 22)
SSH = {'rc': 128, 'window': W, 'boot_id': 'B', 'stderr': 'ssh: connect to host 140.82.121.3 port 22: Connection timed out',
       'sockets': [{'pid': 710, 'start': 9002, 'comm': 'ssh', 'quad': QS, 'states': ['SYN_SENT']}],
       'klog': [kl(QS, 2000), kl(QS, 3000), kl(QS, 5000)], 'proxy': [], 'relay': []}
case('G09 ssh: linked by C1 quad', G.link_verdict(SSH), ('DENIED_POLICY', 'linked_kernel'))
GQ = ('127.0.0.2', 51000, '127.0.0.2', 39999)
OQ = ('127.0.0.2', 52000, '127.0.0.2', 3128)
PROXY = {'rc': 128, 'window': W, 'boot_id': 'B', 'stderr': 'CONNECT tunnel failed, response 403',
         'sockets': [{'pid': 720, 'start': 9003, 'comm': 'git-remote-http', 'quad': GQ, 'states': ['ESTABLISHED']}],
         'klog': [], 'proxy': [{'peer_port': 52000, 'target': 'github.com:443', 'outcome': 'NOT_ALLOWED', 'ts': 4000}],
         'relay': [{'git_quad': GQ, 'own_quad': OQ, 'found': True}]}
case('G10 proxy: git socket -> relay -> proxy record', G.link_verdict(PROXY), ('DENIED_POLICY', 'linked_proxy'))

# Отрицательные
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
d['rc'] = 0
case('G16 git rc 0 -> NOT_PROVEN', G.link_verdict(d), ('NOT_PROVEN', 'git_rc_0'))
d = copy.deepcopy(DIRECT)
d['klog'] = []
case('G17 git socket without kernel line -> NOT_PROVEN', G.link_verdict(d),
     ('NOT_PROVEN', 'git_socket_without_kernel_line'))
d = copy.deepcopy(DIRECT)
d['sockets'][0]['start'] = None
case('G18 socket without starttime (pid reuse unknown) -> NOT_PROVEN', G.link_verdict(d),
     ('NOT_PROVEN', 'socket_without_pid_start'))
d = copy.deepcopy(PROXY)
d['relay'][0]['found'] = False
case('G19 relay did not find git socket -> NOT_PROVEN', G.link_verdict(d), ('NOT_PROVEN', 'relay_git_socket_not_found'))
d = copy.deepcopy(PROXY)
d['proxy'].append({'peer_port': 53000, 'target': 'github.com:443', 'outcome': 'NOT_ALLOWED', 'ts': 5000})
case('G20 extra proxy record without pair -> NOT_PROVEN', G.link_verdict(d), ('NOT_PROVEN', 'proxy_record_unlinked'))
d = copy.deepcopy(PROXY)
d['proxy'][0]['outcome'] = 'ALLOWED'
case('G21 linked proxy record ALLOWED -> NOT_PROVEN', G.link_verdict(d), ('NOT_PROVEN', 'proxy_record_not_refusal'))
d = copy.deepcopy(PROXY)
d['relay'][0]['git_quad'] = ('127.0.0.2', 51999, '127.0.0.2', 39999)
case('G22 relay quad is not a git socket -> NOT_PROVEN', G.link_verdict(d), ('NOT_PROVEN', 'relay_quad_not_git_socket'))
d = copy.deepcopy(PROXY)
d['proxy'] = []
case('G23 relay connection without proxy record -> NOT_PROVEN', G.link_verdict(d),
     ('NOT_PROVEN', 'relay_without_proxy_record'))
d = copy.deepcopy(PROXY)
d['proxy'].append(dict(d['proxy'][0], ts=4500))
case('G24 two proxy records on one port -> NOT_PROVEN', G.link_verdict(d), ('NOT_PROVEN', 'proxy_two_records_one_port'))
# Единственность больше не связывает (REL152): ssh без С1 и с одной четвёркой в окне
d = copy.deepcopy(SSH)
d['sockets'] = []
case('G25 ssh unique quad without C1 -> NOT_PROVEN (no uniqueness rule)', G.link_verdict(d),
     ('NOT_PROVEN', 'kernel_line_unlinked'))
# Прокси: «response 403» и одна запись без переходника -> NOT_PROVEN
d = copy.deepcopy(PROXY)
d['relay'] = []
case('G26 proxy 403 + single record, no relay -> NOT_PROVEN', G.link_verdict(d), ('NOT_PROVEN', 'proxy_record_unlinked'))
# Журнал pb1trial4: нет С1, нет полного stderr, нет переходника
P4 = {'rc': 124, 'window': W, 'boot_id': 'B', 'stderr': '', 'sockets': [],
      'klog': [kl(Q4, 2000), kl(Q4, 3000)], 'proxy': [], 'relay': []}
case('G27 pb1trial4-like facts -> NOT_PROVEN', G.link_verdict(P4), 'NOT_PROVEN')
case('G28 no records at all -> NOT_PROVEN', G.link_verdict(dict(P4, klog=[])), ('NOT_PROVEN', 'no_refusal_record'))
case('G29 bad window -> NOT_PROVEN', G.link_verdict(dict(DIRECT, window=(5, 5))), ('NOT_PROVEN', 'bad_window'))
case('G30 missing field -> NOT_PROVEN', G.link_verdict({'rc': 1}), 'NOT_PROVEN')

print(f'ZPROBE_GITLINK_TESTS {len(OK)}/{len(OK) + len(BAD)} ' + ('PASS' if not BAD else 'FAIL'))
sys.exit(1 if BAD else 0)
