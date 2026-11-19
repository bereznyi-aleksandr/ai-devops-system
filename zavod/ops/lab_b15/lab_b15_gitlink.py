#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/lab_b15/lab_b15_gitlink.py
# ВЕРСИЯ: v0.2  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-19 12:42 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 13:05 +02:00
# v0.2 (REL154): попытка передаёт правилу признак завершения git и итог опроса С1; шаблон байтов — G.connect_bytes.
# ИСПОЛНИТЕЛЬ: Claude (терминал zavod, пускатель)
# НАЗНАЧЕНИЕ: опыт B15 в CI на ubuntu-24.04 (git 2.43, как на сервере; аудит ChatGPT REL153 L-355-REL153-01): работает
#   ли связь попытки push с записью стены на настоящем Linux. Стена — правило iptables LOG+DROP к немому адресу
#   192.0.2.10 (TEST-NET, наружу ничего не уходит); строки ядра с префиксом «zavod-egress-refused ». Проверяется:
#   A direct — http.curloptResolve на немой адрес, С1 (zprobe_sockwatch) и С3 → DENIED_POLICY; строка libcurl с полной
#   четвёркой (свой адрес не 0.0.0.0); B ssh — С1+С3 → DENIED_POLICY; C чужой процесс в окне → NOT_PROVEN;
#   D байты запроса git к HTTP-посреднику (поддельный посредник 127.0.0.1 отвечает 403) равны шаблону пробы
#   connect_equiv. Это лаборатория, не проба сервера: tcp_syn_retries=3 только здесь, чтобы ждать ~15 с, а не ~127 с.
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'server', 'probes'))
import zprobe_gitlink as G  # noqa: E402
import zprobe_rules as R  # noqa: E402
import zprobe_sockwatch as W  # noqa: E402

DEAD_IP = '192.0.2.10'
OK, BAD = [], []


def case(name, cond, detail=''):
    (OK if cond else BAD).append(name)
    print(('LAB PASS ' if cond else 'LAB FAIL ') + name + (f' | {detail}' if detail else ''), flush=True)


def sh(*a, check=True):
    return subprocess.run(list(a), capture_output=True, text=True, check=check)


def kmark(tag):
    sh('sudo', 'sh', '-c', f'echo {tag} > /dev/kmsg')


def klog():
    """dmesg → (метки {tag: ts}, строки стены [{src, spt, dst, dpt, ts, boot}]); ts — мкс часов printk."""
    out, marks = [], {}
    for line in sh('sudo', 'dmesg').stdout.splitlines():
        m = re.match(r'\[\s*(\d+)\.(\d{6})\]\s(.*)$', line)
        if not m:
            continue
        ts, msg = int(m.group(1)) * 1000000 + int(m.group(2)), m.group(3)
        if msg.startswith('zlab-mark-'):
            marks[msg.strip()] = ts
            continue
        f = R.parse_klog(msg)
        if f and f.get('proto') == 'TCP':
            out.append(dict(f, ts=ts, boot=BOOT))
    return marks, out


def repo():
    d = tempfile.mkdtemp(prefix='b15lab_')
    for a in (['init', '-q'], ['-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-q', '--allow-empty', '-m', 't']):
        sh('git', '-C', d, *a)
    return d


def attempt(tag, argv, env_extra, extra_proc=None):
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GIT_TRACE_CURL='1', GIT_TRACE_CURL_NO_DATA='1', **env_extra)
    kmark(f'zlab-mark-{tag}-start')
    p = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, env=env)
    w = W.Watch(p.pid, 0.02).start()
    side = threading.Thread(target=extra_proc, daemon=True) if extra_proc else None
    if side:
        side.start()
    try:
        _, err = p.communicate(timeout=120)
    except subprocess.TimeoutExpired:
        p.kill()
        _, err = p.communicate()
    w.stop()
    if side:
        side.join(60)
    time.sleep(1)
    kmark(f'zlab-mark-{tag}-end')
    marks, kl = klog()
    win = (marks.get(f'zlab-mark-{tag}-start'), marks.get(f'zlab-mark-{tag}-end'))
    att = {'rc': p.returncode, 'exited': p.returncode is not None, 'window': win, 'boot_id': BOOT, 'stderr': err,
           'sockets': w.sockets(), 'watch': {'polls': w.polls, 'errors': w.errors, 'stopped': not w._th.is_alive()},
           'klog': kl, 'proxy': []}
    return att, w, err


def stranger():
    """Чужой процесс (не потомок git) стучится к немому адресу в окне попытки."""
    subprocess.run([sys.executable, '-I', '-c',
                    'import socket;s=socket.socket();s.settimeout(6)\ntry: s.connect(("%s",443))\nexcept OSError: pass'
                    % DEAD_IP], timeout=30)


def fake_proxy_capture(rp, ver):
    srv = socket.socket()
    srv.bind(('127.0.0.1', 0))
    srv.listen(1)
    got = []

    def serve():
        c, _ = srv.accept()
        c.settimeout(5)
        data = b''
        while b'\r\n\r\n' not in data:
            ch = c.recv(4096)
            if not ch:
                break
            data += ch
        got.append(data)
        c.sendall(b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
        c.close()
    t = threading.Thread(target=serve, daemon=True)
    t.start()
    p = subprocess.run(['git', '-C', rp, '-c', f'http.proxy=http://127.0.0.1:{srv.getsockname()[1]}', 'push',
                        'https://github.com/octocat/Hello-World.git', 'HEAD:refs/heads/zprobe-lab'],
                       capture_output=True, text=True, timeout=30, env=dict(os.environ, GIT_TERMINAL_PROMPT='0'))
    t.join(5)
    return p, got


with open('/proc/sys/kernel/random/boot_id', encoding='ascii') as fh:
    BOOT = fh.read().strip()
VER = sh('git', '--version').stdout.strip()
print('LAB_GIT', VER, flush=True)
m = re.match(r'git version (\S+)', VER)
GITV = m.group(1) if m else '?'
LIBC = sh('dpkg-query', '-W', '-f=${Version}', 'libcurl3t64-gnutls', check=False).stdout.strip() or '?'
print('LAB_LIBCURL_GNUTLS', LIBC, flush=True)
EXPECT = os.environ.get('B15_LAB_EXPECT_GIT')
if EXPECT:
    case(f'V1 git version as on server ({EXPECT}*)', GITV.startswith(EXPECT), GITV)
sh('sudo', 'sysctl', '-q', '-w', 'net.ipv4.tcp_syn_retries=3')
sh('sudo', 'iptables', '-I', 'OUTPUT', '1', '-d', DEAD_IP, '-p', 'tcp', '-j', 'DROP')
sh('sudo', 'iptables', '-I', 'OUTPUT', '1', '-d', DEAD_IP, '-p', 'tcp', '-j', 'LOG', '--log-prefix', 'zavod-egress-refused ')
RP = repo()

# A direct
a, w, err = attempt('A', ['git', '-C', RP, '-c', f'http.curloptResolve=github.com:443:{DEAD_IP}', '-c', 'http.proxy=',
                          'push', 'https://github.com/octocat/Hello-World.git', 'HEAD:refs/heads/zprobe-lab'], {})
v = G.link_verdict(a)
case('A1 direct: git rc != 0', a['rc'] not in (0, None), a['rc'])
case('A2 direct: pinned address used (Added … to DNS cache)', f'Added github.com:443:{DEAD_IP}' in err)
case('A3 direct: C1 saw git socket SYN_SENT to dead address',
     any(s['quad'][2] == DEAD_IP and 'SYN_SENT' in s['states'] for s in a['sockets']),
     [(s['comm'], s['quad'], s['states']) for s in a['sockets']])
c2 = G.parse_c2(err)
case('A4 direct: transfer-library line with full four-tuple (own address not 0.0.0.0)', bool(c2), c2)
case('A5 direct: verdict DENIED_POLICY', v == ('DENIED_POLICY', 'linked_kernel'), (v, w.polls, w.errors))
# B ssh
b, w, err = attempt('B', ['git', '-C', RP, 'push', f'ssh://git@{DEAD_IP}/x/y.git', 'HEAD:refs/heads/zprobe-lab'],
                    {'GIT_SSH_COMMAND': 'ssh -v -F /dev/null -o BatchMode=yes -o ConnectTimeout=8 '
                                        '-o StrictHostKeyChecking=no'})
v = G.link_verdict(b)
case('B1 ssh: C1 saw ssh socket to dead address port 22',
     any(s['quad'][2] == DEAD_IP and s['quad'][3] == 22 for s in b['sockets']),
     [(s['comm'], s['quad'], s['states']) for s in b['sockets']])
case('B2 ssh: verdict DENIED_POLICY', v == ('DENIED_POLICY', 'linked_kernel'), (v, w.polls, w.errors))
# C чужой процесс в окне
c, w, err = attempt('C', ['git', '-C', RP, '-c', f'http.curloptResolve=github.com:443:{DEAD_IP}', '-c', 'http.proxy=',
                          'push', 'https://github.com/octocat/Hello-World.git', 'HEAD:refs/heads/zprobe-lab'], {},
                    extra_proc=stranger)
v = G.link_verdict(c)
case('C1 stranger process in window -> NOT_PROVEN kernel_line_unlinked', v == ('NOT_PROVEN', 'kernel_line_unlinked'), v)
# D байты git к посреднику
p, got = fake_proxy_capture(RP, GITV)
want = G.connect_bytes(GITV)
case('D1 git to proxy: one request, exactly the connect_equiv template', got == [want], got)
case('D2 git reports CONNECT tunnel failed, response 403', 'CONNECT tunnel failed, response 403' in p.stderr,
     p.stderr.strip()[-200:])

sh('sudo', 'iptables', '-D', 'OUTPUT', '-d', DEAD_IP, '-p', 'tcp', '-j', 'LOG', '--log-prefix', 'zavod-egress-refused ',
   check=False)
sh('sudo', 'iptables', '-D', 'OUTPUT', '-d', DEAD_IP, '-p', 'tcp', '-j', 'DROP', check=False)
print(f'B15_LAB {len(OK)}/{len(OK) + len(BAD)} ' + ('PASS' if not BAD else 'FAIL'), flush=True)
sys.exit(1 if BAD else 0)
