#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/pb1_session.py
# ВЕРСИЯ: v1.0  СТАТУС: DRAFT
# v1.0 (2026-11-19 13:48 +02:00, выпуск B15, аудит ChatGPT REL155 AGREED; DECISION_B15_PUSH_AND_START v0.5): попытки
#   push_https_direct и push_ssh идут через run_watched() — git в своей группе процессов, опрос его сокетов С1 (/proc,
#   20 мс, класс Watch — копия zprobe_sockwatch.py) и все строки libcurl «connect to … from … port … failed» (С2) из
#   полного вывода; факты rc, exited, timed_out, raw_rc, watch {polls, errors, stopped}, sockets, c2_lines. Попытка
#   push_https_proxy заменена пробой push_proxy_equiv (вид proxy_equiv): сеанс сам шлёт посреднику байты CONNECT,
#   которые шлёт git <версия> (connect_bytes), и читает ответ целиком; это не git push (фраза 3.5.5.1 — редакция
#   REL154 п. 2, подпись оператора). Переходник Relay и run_git убраны (переходник невозможен, REL153). Блоки
#   «zprobe_gitlink» и «zprobe_sockwatch» ниже — копии модулей байт в байт (тест равенства в test_zprobe.py):
#   выпуск закрепляет файлы суммами, сеанс самодостаточен.
# v0.9 (2026-11-13 08:17 +02:00, аудит R10 L-R10-02): переходник сверяет и поколение процессов — время запуска
#   (/proc/<pid>/stat, поле 22) git при set_git и в момент проверки, клиента до и после обхода цепочки; номер,
#   доставшийся новому процессу, даёт chain_ok=false (исход NOT_PROVEN), не допуск.
# v0.8 (2026-11-13 07:24 +02:00, аудит R7 C-R7-01): переходник обслуживает только git этой попытки: git запускается
#   через Popen, его номер процесса (PID) передаётся переходнику; у каждого клиента файла-сокета переходник берёт
#   от ядра PID и uid (SO_PEERCRED) и по /proc поднимается по родителям до PID git; цепочки нет — соединение
#   закрывается без SOCKS (err peer_not_git). Цепочка [PID, имя] и uid печатаются в facts.relay.conns[].peer,
#   PID git — в facts.git_pid; правила сверяют их и требуют в выводе git отказ SOCKS5 с кодом 2.
# v0.7 (2026-11-13 07:08 +02:00, аудит R6B C-R6-01): git через посредника идёт только через переходник сеанса (Relay):
#   сокет AF_UNIX в новой папке сеанса, SOCKS5 от git, своё TCP-соединение к посреднику и CONNECT; точные адрес и
#   порт каждого соединения переходника (getsockname) и ответ посредника печатаются в facts.relay — правила ищут
#   запись посредника именно с этим адресом:портом. Прямой http-путь git к посреднику убран.
# v0.6 (2026-11-13 05:59 +02:00, аудит R5): C-R5-01 у попытки через посредника — свой адрес src (getsockname), у
#   git через посредника — адрес proxy_src, который ядро выберет для 127.0.0.2; правила сверяют с ними адрес
#   собеседника в журнале посредника; M-R5-04 рабочая папка git создаётся только новой (mkdir), pb1.txt — только
#   новым файлом (O_EXCL, O_NOFOLLOW); уже есть — сбой подготовки, PB1_DONE и конец сеанса (ничего не заменено).
# v0.5 (2026-11-12 23:41 +02:00, аудит R4): перед каждой попыткой строка «PB1_BEGIN {seq, name}» и пауза 0,25 с,
#   после попытки пауза 0,25 с и строка «PB1» — по меткам journald этих двух строк хост строит окно попытки
#   (C-R4-01, M-R4-03); tcp — адрес источника берётся заранее пустым UDP connect (пакетов нет), сокет привязан к
#   этому адресу и порту 0, печатаются src и lport.
# ДАТА СОЗДАНИЯ: 2026-11-12 19:03 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-12 23:14 +02:00 (v0.4 по аудиту R3: M-R3-04 — каждая
#   строка PB1 несёт номер seq 1..N подряд, хост отвергает повтор и пропуск; tcp — сокет сначала привязан к порту 0,
#   печатается свой порт lport, его сверяют со строкой отказа ядра «zavod-egress-refused» (наблюдатель снаружи
#   клетки); v0.2: аудит ChatGPT STAGE355 R1 —
#   сеанс печатает только факты, исход ставят правила zprobe_rules.py снаружи (C-01); подготовка git проверяется,
#   окружение git — только разрешённые имена, пустые настройки (M-04); пути ключей без O_DIRECTORY (M-05); адреса
#   GitHub IPv4/IPv6 и имена приходят планом от хоста (M-06, L-10))
# ИСПОЛНИТЕЛЬ: Claude (чаты 87eee078-952e-4855-8936-7f4d449aa9ac, c7307e9c-8e0e-4e24-997c-12d9fd3b0c71)
# НАЗНАЧЕНИЕ: проба ПБ-1 (протокол Завода v4 ред12, И.13, И.13а; карта 3.5.5.1, 3.5.5.2; DESIGN_3_5_5_PB1_v0_2.md).
#   Запускается ВНУТРИ настоящей клетки zagent@<аренда> вместо заглушки сеанса (временное дополнение только этой
#   аренды, его ставит zprobe_runner.py). Пробует записать в GitHub: git push (через посредника, напрямую, ssh),
#   прямые TCP 22/443 к каждому адресу плана, CONNECT посредника к каждому имени и к адресу, обычный GET.
#   Печатает строки «PB1 <JSON фактов>», в конце PB1_DONE, потом ждёт остановки. Исход «отказ» сам не ставит.
# ОГРАНИЧЕНИЯ: ничего не читает из путей ключей — только код ошибки открытия, файл сразу закрывается; значения
#   переменных окружения не печатает (только имена, подходящие под образец плана). План — argv[1]: base64 JSON
#   {challenge, targets, gh_names, cred_paths, cred_env_re, repo_https, repo_path}.
import base64
import errno
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time

PROXY = ('127.0.0.2', 3128)
DIRECT_PUSH_S = 180     # B15 П3: предел push_https_direct (13 адресов, повторы SYN ~127 с на адрес); = zprobe_runner
KEEP = re.compile(r'(connect|Connected|CONNECT|Trying|fatal|error|refused|not permitted|denied|resolve|SOCKS)', re.I)


SEQ = [0]
CUR = [None]
GAP = 0.25   # пауза между строкой сеанса и действием: метки journald окна заведомо охватывают действие


def begin(name):
    SEQ[0] += 1
    CUR[0] = name
    print('PB1_BEGIN ' + json.dumps({'seq': SEQ[0], 'name': name}, sort_keys=True, ensure_ascii=True), flush=True)
    time.sleep(GAP)


def out(name, kind, facts):
    if CUR[0] != name:                   # строка без своего начала — хост не построит окно, попытка NOT_PROVEN
        name = name + '_without_begin'
    CUR[0] = None
    time.sleep(GAP)
    print('PB1 ' + json.dumps({'seq': SEQ[0], 'name': name, 'kind': kind, 'facts': facts}, sort_keys=True,
                              ensure_ascii=True), flush=True)


def ename(e):
    return errno.errorcode.get(getattr(e, 'errno', None) or 0, type(e).__name__)


def tag(ip):
    return ip.replace(':', '-')


def tail(text):
    lines = [ln for ln in text.splitlines() if KEEP.search(ln)]
    return ''.join(ch if 32 <= ord(ch) < 127 or ch == '\n' else '?' for ch in '\n'.join(lines[-40:]))[-3000:]


def route_src(ip, fam):
    """Адрес источника, который ядро выберет для ip: UDP connect пакетов не шлёт, только выбирает маршрут."""
    u = socket.socket(fam, socket.SOCK_DGRAM)
    try:
        u.connect((ip, 9))
        return u.getsockname()[0]
    except OSError:
        return None
    finally:
        u.close()


def tcp(ip, port):
    fam = socket.AF_INET6 if ':' in ip else socket.AF_INET
    t0 = time.monotonic()
    s = socket.socket(fam, socket.SOCK_STREAM)
    s.settimeout(8)
    lport, src = None, route_src(ip, fam)
    try:
        s.bind((src or ('::' if fam == socket.AF_INET6 else '0.0.0.0'), 0))   # пакетов нет; адрес и порт — до connect
        lport = s.getsockname()[1]
        s.connect((ip, port))
        e = 'connected'
    except socket.timeout:
        e = 'timeout'
    except OSError as x:
        e = ename(x)
    finally:
        s.close()
    return {'ip': ip, 'port': port, 'errno': e, 'ms': int((time.monotonic() - t0) * 1000), 'lport': lport, 'src': src}


def proxy(mode, target):
    line = (f'CONNECT {target} HTTP/1.1\r\nHost: {target}' if mode == 'connect'
            else f'GET http://{target}/ HTTP/1.1\r\nHost: {target}')
    f = {'mode': mode, 'target': target, 'lport': None, 'status': None, 'err': None}
    try:
        with socket.create_connection(PROXY, timeout=15) as s:
            f['src'], f['lport'] = s.getsockname()[:2]
            s.sendall(line.encode('ascii') + b'\r\n\r\n')
            data = s.recv(200)
        m = re.match(rb'HTTP/1\.[01] (\d{3}) ', data)
        f['status'] = int(m.group(1)) if m else None
        f['err'] = None if m else 'bad_answer'
    except socket.timeout:
        f['err'] = 'timeout'
    except OSError as x:
        f['err'] = ename(x)
    return f


# ==== BEGIN zprobe_gitlink (копия модуля байт в байт, от TCP_STATES до конца) ====
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
    'watch': {'polls', 'errors', 'stopped'} (опрос С1), 'window': (от, до) мкс монотонных, 'boot_id',
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
# ==== END zprobe_gitlink ====


# ==== BEGIN zprobe_sockwatch (копия модуля от _read до конца, без префикса «G.») ====
def _read(path):
    try:
        with open(path, encoding='ascii', errors='replace') as fh:
            return fh.read()
    except OSError:
        return None


def starttime(pid):
    s = _read(f'/proc/{pid}/stat')
    if not s or ')' not in s:
        return None
    try:
        return int(s[s.rindex(')') + 2:].split()[19])
    except (ValueError, IndexError):
        return None


def comm(pid):
    return (_read(f'/proc/{pid}/comm') or '').strip()


def tree(root):
    """PID корня и всех потомков (по /proc/<pid>/task/<tid>/children)."""
    out, todo = [], [root]
    while todo:
        p = todo.pop()
        out.append(p)
        try:
            tids = os.listdir(f'/proc/{p}/task')
        except OSError:
            continue
        for t in tids:
            ch = _read(f'/proc/{p}/task/{t}/children') or ''
            todo.extend(int(x) for x in ch.split() if x.isdigit())
    return out


def fd_links(pid):
    try:
        names = os.listdir(f'/proc/{pid}/fd')
    except OSError:
        return []
    out = []
    for n in names:
        try:
            out.append(os.readlink(f'/proc/{pid}/fd/{n}'))
        except OSError:
            continue
    return out


def net_table():
    t = {}
    for f in ('/proc/self/net/tcp', '/proc/self/net/tcp6'):
        s = _read(f)
        if s:
            t.update(parse_net_tcp(s))
    return t


class Watch:
    """Опрос дерева git раз в interval секунд в отдельном потоке до stop(). Итог — sockets(): список
    {pid, start, comm, inode, quad, states, first, last} (время — CLOCK_MONOTONIC в микросекундах)."""

    def __init__(self, root_pid, interval=0.02):
        self.root, self.interval = root_pid, interval
        self._seen, self._halt = {}, threading.Event()
        self.polls, self.errors = 0, 0
        self._th = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._th.start()
        return self

    def _run(self):
        while not self._halt.is_set():
            self.poll()
            self._halt.wait(self.interval)
        self.poll()

    def poll(self):
        try:
            now = time.clock_gettime_ns(time.CLOCK_MONOTONIC) // 1000
            pids = tree(self.root)
            want = {}
            for p in pids:
                st = starttime(p)
                if st is None:
                    continue
                for ino in socket_inodes(fd_links(p)):
                    want[ino] = (p, st)
            if want:
                net = net_table()
                for ino, (p, st) in want.items():
                    row = net.get(ino)
                    if row is None:
                        continue
                    key = (p, st, ino)
                    rec = self._seen.get(key)
                    if rec is None:
                        rec = self._seen[key] = {'pid': p, 'start': st, 'comm': comm(p), 'inode': ino,
                                                 'quad': row['quad'], 'states': [], 'first': now, 'last': now}
                    if rec['quad'] != row['quad']:
                        rec['quad_changed'] = True
                    if row['state'] not in rec['states']:
                        rec['states'].append(row['state'])
                    rec['last'] = now
            self.polls += 1
        except Exception:   # noqa: BLE001 — сбой опроса не ломает попытку; сокет без пары даст NOT_PROVEN
            self.errors += 1

    def stop(self):
        self._halt.set()
        self._th.join(5)
        return self

    def sockets(self):
        return [dict(r) for r in self._seen.values() if not r.get('quad_changed')]
# ==== END zprobe_sockwatch ====


def git_env(home, extra):
    env = {'PATH': '/usr/bin:/bin', 'HOME': home, 'LANG': 'C.UTF-8', 'GIT_CONFIG_NOSYSTEM': '1',
           'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_TERMINAL_PROMPT': '0', 'GIT_ASKPASS': '/bin/false',
           'SSH_ASKPASS': '/bin/false', 'GIT_TRACE_CURL': '1', 'GIT_TRACE_CURL_NO_DATA': '1',
           'GIT_AUTHOR_NAME': 'pb1', 'GIT_AUTHOR_EMAIL': 'pb1@invalid', 'GIT_COMMITTER_NAME': 'pb1',
           'GIT_COMMITTER_EMAIL': 'pb1@invalid'}
    env.update(extra)
    return env


def run(args, cwd, env, timeout=60):
    """B15 П3 (Ф3): своя группа процессов; при тайм-ауте убивается ВСЯ группа (git-remote-https и ssh тоже — в pb1trial4
    дочерний процесс пережил git и слал SYN в окно следующей попытки), а частичный вывод (след «Trying …») сохраняется."""
    try:
        p = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, start_new_session=True)
    except FileNotFoundError:
        return 127, '', 'absent'
    try:
        so, se = p.communicate(timeout=timeout)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        killpg(p.pid)
        so, se = p.communicate()
        rc, se = 124, (se or '') + '\nzprobe: timeout'
    killpg(p.pid)            # остатки группы (дети, пережившие родителя) — до следующей попытки
    return rc, so, se


def killpg(pgid):
    try:
        os.killpg(pgid, 9)
    except (ProcessLookupError, PermissionError):
        pass


def own_group_procs():
    """B15 П7: процессы своей группы (cgroup v2) с PID, starttime, ppid, comm — чтение /proc своего uid."""
    with open('/proc/self/cgroup', encoding='ascii') as fh:
        path = fh.read().strip().split('::', 1)[1]
    with open('/sys/fs/cgroup' + path + '/cgroup.procs', encoding='ascii') as fh:
        pids = [int(x) for x in fh.read().split()]
    out_ = []
    for pid in pids:
        try:
            with open(f'/proc/{pid}/stat', encoding='ascii', errors='replace') as fh:
                st = fh.read()
        except OSError:
            continue                         # процесс уже завершился
        comm, rest = st[st.index('(') + 1:st.rindex(')')], st[st.rindex(')') + 2:].split()
        out_.append({'pid': pid, 'ppid': int(rest[1]), 'start': int(rest[19]), 'comm': comm})
    return out_


def quiet_group(limit=10.0):
    """B15 П7: ждать, пока в группе сеанса останется только сам сеанс; не дождались — False и снимок группы."""
    me, t_end = os.getpid(), time.monotonic() + limit
    while True:
        procs = own_group_procs()
        if all(x['pid'] == me for x in procs):
            return True, procs
        if time.monotonic() > t_end:
            return False, procs
        time.sleep(0.05)


C2_MAX = 400    # строк С2 больше — c2_truncated, правила дают NOT_PROVEN (у direct 13 адресов — десятки строк)


def run_watched(args, cwd, env, timeout):
    """B15 С1/С2 (REL155 L-02: происхождение фактов). git — в своей группе процессов; сразу после запуска — опрос
    сокетов git и его потомков (Watch, 20 мс) до сбора процесса. Факты: rc — код git (124 — тайм-аут, группа убита),
    raw_rc — код, который вернула ОС при сборе процесса (Popen.returncode), exited — True, только когда процесс git
    собран (returncode не None), timed_out, watch {polls, errors, stopped} — счётчики самого опроса, sockets — сокеты С1
    ({pid, start, comm, inode, quad, states, first, last}), c2_lines — ВСЕ строки libcurl «connect to … port … from …
    port … failed» полного вывода git (не хвоста), stderr_tail — справочно."""
    f = {'rc': None, 'raw_rc': None, 'exited': False, 'timed_out': False, 'absent': False,
         'watch': {'polls': 0, 'errors': 0, 'stopped': False}, 'sockets': [], 'c2_lines': [], 'c2_truncated': False,
         'stderr_tail': ''}
    try:
        p = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, encoding='utf-8', errors='replace', start_new_session=True)
    except FileNotFoundError:
        f.update(rc=127, absent=True)
        return f
    w = Watch(p.pid).start()
    try:
        _, se = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        f['timed_out'] = True
        killpg(p.pid)
        _, se = p.communicate()
    w.stop()
    killpg(p.pid)            # остатки группы (дети, пережившие git) — до следующей попытки
    se = se or ''
    f['raw_rc'] = p.returncode
    f['exited'] = p.returncode is not None
    f['rc'] = 124 if f['timed_out'] else p.returncode
    f['watch'] = {'polls': w.polls, 'errors': w.errors, 'stopped': not w._th.is_alive()}
    f['sockets'] = [dict(s, quad=list(s['quad'])) for s in w.sockets()]
    lines = [m.group(0) for m in _C2.finditer(se)]
    f['c2_lines'], f['c2_truncated'] = lines[:C2_MAX], len(lines) > C2_MAX
    f['stderr_tail'] = tail(se + ('\nzprobe: timeout' if f['timed_out'] else ''))
    return f


def push_proxy_equiv(plan, repo, env):
    """B15 (REL154 M-01, REL155 AGREED): проба, равная по байтам запросу git push к посреднику. Версия — git --version
    этой клетки; байты — connect_bytes(версия) (сняты с git 2.43); свой сокет к 127.0.0.2:3128, его адрес, порт и
    собеседник — от ядра (getsockname/getpeername); ответ читается до пустой строки (не больше 8 КБ). Это не git push."""
    rc, so, _ = run(['git', '--version'], repo, env, timeout=10)   # бюджет сеанса: проба ≤ 10 + 15 + 15 с < 62 с
    so = (so or '').strip()
    ver = so[len('git version '):] if rc == 0 and so.startswith('git version ') else None
    f = {'git_version': ver, 'git_version_rc': rc, 'git_proxy': PROXY_URL, 'remote': plan['repo_https'],
         'sent_hex': None, 'own': None, 'reply': {'complete': False, 'status': None, 'error': None, 'head': ''}}
    data = connect_bytes(ver)
    if data is None:
        f['reply']['error'] = 'git_version_unknown'
        return f
    head = b''
    try:
        with socket.create_connection(PROXY, timeout=15) as s:
            src, port = s.getsockname()[:2]
            peer = s.getpeername()[:2]
            f['own'] = {'src': src, 'port': port, 'peer': [peer[0], peer[1]]}
            s.sendall(data)
            f['sent_hex'] = data.hex()
            while b'\r\n\r\n' not in head and len(head) < 8192:
                d = s.recv(8192 - len(head))
                if not d:
                    break
                head += d
    except socket.timeout:
        f['reply']['error'] = 'timeout'
    except OSError as x:
        f['reply']['error'] = ename(x)
    m = re.match(rb'HTTP/1\.[01] (\d{3}) ', head)
    r = f['reply']
    r['complete'] = b'\r\n\r\n' in head
    r['status'] = int(m.group(1)) if m else None
    if r['error'] is None and not (r['complete'] and m):
        r['error'] = 'bad_answer'
    r['head'] = ''.join(chr(b) if 32 <= b < 127 or b in (10, 13) else '?' for b in head[:600])
    return f


def main():
    try:
        plan = json.loads(base64.b64decode(sys.argv[1], validate=True))
        challenge = plan['challenge']
        assert re.fullmatch(r'[0-9a-f]{32}', challenge)
    except Exception as e:  # noqa: BLE001 — любой сбой плана: ни одной попытки, правила дадут NOT_PROVEN
        print('PB1_PLAN_BAD ' + type(e).__name__, flush=True)
        print('PB1_DONE', flush=True)
        return
    rx = re.compile(plan['cred_env_re'], re.I)
    begin('cred_env')
    out('cred_env', 'cred_env', {'found': sorted(k for k in os.environ if rx.search(k))})
    for p in plan['cred_paths']:
        begin('cred_path_' + p.strip('/').replace('/', '_'))
        try:
            fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
            os.close(fd)
            e = 'opened'
        except OSError as x:
            e = ename(x)
        out('cred_path_' + p.strip('/').replace('/', '_'), 'cred_path', {'path': p, 'errno': e})

    targets = plan['targets']
    for ip in targets:
        for port in (22, 443):
            begin(f'tcp_{port}_{tag(ip)}')
            out(f'tcp_{port}_{tag(ip)}', 'tcp', tcp(ip, port))

    # 3.5.5.1 — git push. Хранилище в рабочей папке сеанса, один коммит; подготовка проверяется (аудит M-04).
    home = os.path.join(os.getcwd(), 'pb1-' + challenge[:8])
    repo = os.path.join(home, 'repo')
    begin('git_prep')
    try:                                 # R5 M-04: только новое — существующая папка или файл не заменяются
        os.mkdir(home, 0o700)
        os.mkdir(repo, 0o700)
        fd = os.open(os.path.join(repo, 'pb1.txt'),
                     os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        with os.fdopen(fd, 'w', encoding='ascii') as fh:
            fh.write(challenge + '\n')
    except OSError as x:
        out('git_prep', 'git_prep', {'setup': ename(x)})
        print('PB1_DONE', flush=True)
        return
    env = git_env(home, {})
    prep = {}
    for step, args in (('init', ['git', 'init', '-q']), ('add', ['git', 'add', 'pb1.txt']),
                       ('commit', ['git', 'commit', '-q', '-m', 'pb1 ' + challenge])):
        prep[step] = run(args, repo, env)[0]
    rc, so, _ = run(['git', 'rev-parse', 'HEAD'], repo, env)
    prep['rev_parse'], prep['head'] = rc, so.strip()
    rc, so, _ = run(['git', 'config', '--list', '--show-origin'], repo, env)
    prep['config_list'] = '\n'.join(ln for ln in so.splitlines() if not ln.startswith('file:.git/config'))
    out('git_prep', 'git_prep', prep)

    ref = 'HEAD:refs/heads/zprobe/pb1-' + challenge[:8]
    # B15 (REL154 M-01, REL155 AGREED): git push через посредника не запускается — его заменяет проба push_proxy_equiv
    # с теми же байтами CONNECT; итог пробы — не git push (фраза 3.5.5.1 в редакции REL154 п. 2).
    begin('push_proxy_equiv')
    qb = quiet_group()[0]
    f = push_proxy_equiv(plan, repo, git_env(home, {}))
    f.update(quiet_before=qb, quiet_after=quiet_group()[0])
    out('push_proxy_equiv', 'proxy_equiv', f)
    v = [ip if ':' not in ip else f'[{ip}]' for ip in targets]
    begin('push_https_direct')
    qb = quiet_group()[0]
    f = run_watched(['git', '-c', 'http.curloptResolve=github.com:443:' + ','.join(v), 'push', plan['repo_https'],
                     ref], repo, git_env(home, {}), DIRECT_PUSH_S)
    f.update(via='direct', resolve=targets, quiet_before=qb, quiet_after=quiet_group()[0])
    out('push_https_direct', 'git_push', f)
    v4 = [ip for ip in targets if ':' not in ip][:1]
    begin('push_ssh')
    if shutil.which('ssh', path='/usr/bin:/bin') is None or not v4:
        out('push_ssh', 'git_push', {'via': 'ssh', 'absent': True, 'rc': None, 'stderr_tail': '', 'ip': None})
    else:
        ssh = ('ssh -v -F /dev/null -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no '
               '-o UserKnownHostsFile=/dev/null -o IdentitiesOnly=yes -o IdentityFile=/dev/null')
        qb = quiet_group()[0]
        f = run_watched(['git', 'push', f'ssh://git@{v4[0]}/{plan["repo_path"]}', ref], repo,
                        git_env(home, {'GIT_SSH_COMMAND': ssh}), 60)
        f.update(via='ssh', ip=v4[0], quiet_before=qb, quiet_after=quiet_group()[0])
        out('push_ssh', 'git_push', f)

    # 3.5.5.2 — API GitHub: CONNECT по каждому имени и по адресу, обычный GET.
    for name in plan['gh_names']:
        begin('connect_' + name)
        out('connect_' + name, 'proxy', proxy('connect', name + ':443'))
    seen = set()
    for ip in targets:
        fam = ':' in ip
        if fam not in seen:
            seen.add(fam)
            begin('connect_ip_' + tag(ip))
            out('connect_ip_' + tag(ip), 'proxy', proxy('connect', (f'[{ip}]' if fam else ip) + ':443'))
    begin('plain_get')
    out('plain_get', 'proxy', proxy('plain', 'api.github.com'))
    print('PB1_DONE', flush=True)


if __name__ == '__main__':
    main()
    while True:
        time.sleep(3600)
