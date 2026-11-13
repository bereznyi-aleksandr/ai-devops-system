#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/pb1_session.py
# ВЕРСИЯ: v0.9  СТАТУС: DRAFT
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
import json
import os
import re
import select
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time

PROXY = ('127.0.0.2', 3128)
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


class Relay:
    """R6 C-R6-01: git через посредника идёт через этот переходник — сокет AF_UNIX в новой папке сеанса (сетевой
    фильтр его не касается), SOCKS5 от libcurl git (socks5h://localhost/<путь>), дальше своё TCP-соединение к
    посреднику и запрос CONNECT. Порт этого соединения переходник знает точно (getsockname) — правила ищут в
    журнале посредника запись именно с этим адресом и портом. Ответ посредника не 200 — git получает отказ SOCKS
    (код 2), байты не идут. 200 — байты идут в обе стороны (исход FAIL увидят правила и снимки веток)."""

    def __init__(self, path):
        self.path, self.conns, self.err, self.git_pid = path, [], None, None
        self.git_start = None
        self.ready = threading.Event()   # R7 C-01: PID git известен — только после этого клиент обслуживается
        self.srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.srv.bind(path)               # путь новый: папка сеанса создана только что (mkdir); занят — OSError
        self.srv.listen(4)
        self.srv.settimeout(0.2)
        self.stop = threading.Event()
        self.th = threading.Thread(target=self.loop, daemon=True)
        self.th.start()

    def loop(self):
        while not self.stop.is_set():
            try:
                c, _ = self.srv.accept()
            except socket.timeout:
                continue
            except OSError as x:
                self.err = ename(x)
                return
            with c:
                self.serve(c)

    def set_git(self, pid):
        self.git_start = self.start_time(pid) if isinstance(pid, int) else None   # R10 L-02: поколение git
        self.git_pid = pid
        self.ready.set()

    @staticmethod
    def start_time(pid):
        """R10 L-02: время запуска процесса (/proc/<pid>/stat, поле 22) — отличает процесс от нового с тем же номером."""
        try:
            with open(f'/proc/{pid}/stat', encoding='ascii', errors='replace') as fh:
                st = fh.read()
            return int(st[st.rindex(')') + 2:].split()[19])
        except (OSError, ValueError, IndexError):
            return None

    @staticmethod
    def chain(pid, top):
        """R7 C-01: от клиента вверх по родителям (/proc/<pid>/status, PPid) до top; → (цепочка [[pid, имя]], дошли)."""
        seen = []
        for _ in range(8):
            try:
                with open(f'/proc/{pid}/status', encoding='ascii', errors='replace') as fh:
                    st = dict(ln.split(':', 1) for ln in fh.read().splitlines() if ':' in ln)
                ppid = int(st.get('PPid', '0').strip() or 0)
            except (OSError, ValueError):
                return seen, False
            seen.append([pid, st.get('Name', '').strip()[:32]])
            if pid == top:
                return seen, True
            if ppid <= 1:
                return seen, False
            pid = ppid
        return seen, False

    @staticmethod
    def need(c, n):
        b = b''
        while len(b) < n:
            d = c.recv(n - len(b))
            if not d:
                raise OSError(errno.ECONNRESET, 'short')
            b += d
        return b

    def serve(self, c):
        f = {'target': None, 'src': None, 'lport': None, 'status': None, 'err': None, 'peer': None}
        self.conns.append(f)
        c.settimeout(15)
        try:                              # R7 C-01: клиент — git этой попытки или его потомок, иначе не обслуживать
            pid, uid, _ = struct.unpack('3i', c.getsockopt(socket.SOL_SOCKET, getattr(socket, 'SO_PEERCRED', 17),
                                                           struct.calcsize('3i')))
            self.ready.wait(5)
            top = self.git_pid
            s0 = self.start_time(pid)
            ch, ok = self.chain(pid, top) if isinstance(top, int) and top > 1 else ([], False)
            gen_ok = (s0 is not None and s0 == self.start_time(pid) and self.git_start is not None
                      and self.git_start == self.start_time(top))   # R10 L-02: те же процессы, не новые с теми номерами
            ok = ok and gen_ok
            f['peer'] = {'pid': pid, 'uid': uid, 'chain': ch, 'chain_ok': ok, 'gen_ok': gen_ok}
        except OSError as x:
            f['err'] = 'peercred_' + ename(x)
            return
        if not ok:
            f['err'] = 'peer_not_git'
            return
        try:
            v, n = self.need(c, 2)
            self.need(c, n)
            if v != 5:
                raise ValueError('socks_version')
            c.sendall(b'\x05\x00')
            v, cmd, _, at = self.need(c, 4)
            if v != 5 or cmd != 1:
                raise ValueError('socks_cmd')
            if at == 3:
                host = self.need(c, self.need(c, 1)[0]).decode('ascii')
            elif at == 1:
                host = socket.inet_ntop(socket.AF_INET, self.need(c, 4))
            elif at == 4:
                host = '[' + socket.inet_ntop(socket.AF_INET6, self.need(c, 16)) + ']'
            else:
                raise ValueError('socks_atyp')
            port = int.from_bytes(self.need(c, 2), 'big')
            f['target'] = f'{host}:{port}'
            u = socket.create_connection(PROXY, timeout=15)
        except (OSError, ValueError, UnicodeError) as x:
            f['err'] = ename(x) if isinstance(x, OSError) else str(x)
            return
        with u:
            f['src'], f['lport'] = u.getsockname()[:2]
            try:
                u.sendall(f'CONNECT {f["target"]} HTTP/1.1\r\nHost: {f["target"]}\r\n\r\n'.encode('ascii'))
                head = b''
                while b'\r\n\r\n' not in head and len(head) < 4096:
                    d = u.recv(4096 - len(head))
                    if not d:
                        break
                    head += d
                m = re.match(rb'HTTP/1\.[01] (\d{3}) ', head)
                f['status'] = int(m.group(1)) if m else None
                if f['status'] != 200:
                    f['err'] = None if m else 'bad_answer'
                    c.sendall(b'\x05\x02\x00\x01' + bytes(6))     # «запрещено правилами»
                    return
                c.sendall(b'\x05\x00\x00\x01' + bytes(6))
                rest = head.split(b'\r\n\r\n', 1)[1]
                if rest:
                    c.sendall(rest)
                self.pipe(c, u)
            except OSError as x:
                f['err'] = ename(x)

    @staticmethod
    def pipe(a, b):
        a.settimeout(None)
        b.settimeout(None)
        socks = [a, b]
        while True:
            r, _, _ = select.select(socks, [], [], 30)
            if not r:
                return
            for s in r:
                d = s.recv(65536)
                if not d:
                    return
                (b if s is a else a).sendall(d)

    def close(self):
        self.stop.set()
        self.th.join(5)
        self.srv.close()
        return {'conns': self.conns, 'err': self.err, 'alive': self.th.is_alive()}


def git_env(home, extra):
    env = {'PATH': '/usr/bin:/bin', 'HOME': home, 'LANG': 'C.UTF-8', 'GIT_CONFIG_NOSYSTEM': '1',
           'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_TERMINAL_PROMPT': '0', 'GIT_ASKPASS': '/bin/false',
           'SSH_ASKPASS': '/bin/false', 'GIT_TRACE_CURL': '1', 'GIT_TRACE_CURL_NO_DATA': '1',
           'GIT_AUTHOR_NAME': 'pb1', 'GIT_AUTHOR_EMAIL': 'pb1@invalid', 'GIT_COMMITTER_NAME': 'pb1',
           'GIT_COMMITTER_EMAIL': 'pb1@invalid'}
    env.update(extra)
    return env


def run(args, cwd, env, timeout=60):
    try:
        p = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout,
                           stdin=subprocess.DEVNULL)
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, '', 'absent'
    except subprocess.TimeoutExpired:
        return 124, '', 'timeout'


def run_git(args, cwd, env, relay, timeout=60):
    """R7 C-01: git через Popen — его PID сразу уходит переходнику (клиенты переходника сверяются с ним)."""
    try:
        p = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
    except FileNotFoundError:
        relay.set_git(None)
        return 127, '', 'absent', None
    relay.set_git(p.pid)
    try:
        so, se = p.communicate(timeout=timeout)
        return p.returncode, so, se, p.pid
    except subprocess.TimeoutExpired:
        p.kill()
        p.communicate()
        return 124, '', 'timeout', p.pid


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
    begin('push_https_proxy')
    sock = os.path.join(home, 'r')        # R6 C-R6-01: переходник git → посредник с точным портом
    try:
        relay = Relay(sock)
    except OSError as x:
        out('push_https_proxy', 'git_push', {'via': 'proxy', 'rc': None, 'stderr_tail': '', 'absent': False,
                                             'git_pid': None,
                                             'relay': {'conns': [], 'err': 'bind_' + ename(x), 'alive': False}})
    else:
        px = 'socks5h://localhost' + sock
        rc, _, se, gpid = run_git(['git', '-c', 'http.proxy=' + px, 'push', plan['repo_https'], ref], repo,
                                  git_env(home, {'https_proxy': px, 'HTTPS_PROXY': px, 'ALL_PROXY': px}), relay)
        out('push_https_proxy', 'git_push', {'via': 'proxy', 'rc': rc, 'stderr_tail': tail(se), 'absent': rc == 127,
                                             'git_pid': gpid, 'relay': relay.close()})
    v = [ip if ':' not in ip else f'[{ip}]' for ip in targets]
    begin('push_https_direct')
    rc, _, se = run(['git', '-c', 'http.curloptResolve=github.com:443:' + ','.join(v), 'push', plan['repo_https'], ref],
                    repo, git_env(home, {}))
    out('push_https_direct', 'git_push', {'via': 'direct', 'rc': rc, 'stderr_tail': tail(se), 'absent': rc == 127,
                                          'resolve': targets})
    v4 = [ip for ip in targets if ':' not in ip][:1]
    begin('push_ssh')
    if shutil.which('ssh', path='/usr/bin:/bin') is None or not v4:
        out('push_ssh', 'git_push', {'via': 'ssh', 'absent': True, 'rc': None, 'stderr_tail': '', 'ip': None})
    else:
        ssh = ('ssh -v -F /dev/null -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no '
               '-o UserKnownHostsFile=/dev/null -o IdentitiesOnly=yes -o IdentityFile=/dev/null')
        rc, _, se = run(['git', 'push', f'ssh://git@{v4[0]}/{plan["repo_path"]}', ref], repo,
                        git_env(home, {'GIT_SSH_COMMAND': ssh}))
        out('push_ssh', 'git_push', {'via': 'ssh', 'absent': False, 'rc': rc, 'stderr_tail': tail(se), 'ip': v4[0]})

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
