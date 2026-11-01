#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/cell/egress_session_probe.py
# ВЕРСИЯ: v0.4  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-01 22:56 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-02 00:13 +02:00 (v0.4: аудит M3310-R1B-03/04 — прямой выход по IPv6; поддомены GitHub через посредник; v0.3: аудит M3310-R1B-01 — проба «соединившийся процесс вышел, команду дописал его потомок»; v0.2: разрешённый адрес — учебный example.com из списка CI)
# ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
# НАЗНАЧЕНИЕ: только для CI (egress_ci.sh): запускается ВНУТРИ настоящей клетки zagent@<аренда> вместо заглушки
#   сессии и пробует двери изнутри: привратник (ПБ-5: повтор номера, чужая аренда, сумма, строгий JSON, текст SQL)
#   и сеть (ПБ-3: прямой выход, свой перевод имён, база, шина D-Bus, посредник со списком адресов).
#   Печатает строки «EGRESS_PROBE имя=итог», в конце EGRESS_PROBE_DONE, потом ждёт остановки.
# ОГРАНИЧЕНИЯ: на сервер не ставится; аренда и вторая аренда приходят из окружения (ZCI_LEASE, ZCI_OTHER).
import hashlib
import json
import os
import socket
import struct
import time

SOCK = os.environ.get('ZAVOD_GATE_SOCKET', '/run/zavod-gate/agent.sock')
LEASE = os.environ['ZCI_LEASE']
OTHER = os.environ['ZCI_OTHER']
PROXY = ('127.0.0.2', 3128)


def out(name, value):
    print(f'EGRESS_PROBE {name}={value}', flush=True)


def gate_raw(raw):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(15)
    try:
        s.connect(SOCK)
        s.sendall(raw)
        data = b''
        while not data.endswith(b'\n'):
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
        return json.loads(data)['result'] if data else 'NO_ANSWER'
    except (OSError, ValueError, KeyError) as e:
        return 'ERROR_' + type(e).__name__
    finally:
        s.close()


def gate(body, nonce=None, lease_id=LEASE, sha=None, extra=None):
    b = body if isinstance(body, str) else json.dumps(body)
    env = {'v': 1, 'lease_id': lease_id, 'nonce': nonce or os.urandom(32).hex(),
           'sha256': sha or hashlib.sha256(b.encode()).hexdigest(), 'body': b}
    if extra:
        env.update(extra)
    return gate_raw((json.dumps(env) + '\n').encode())


def gate_after_exit():
    """Процесс A соединяется и выходит; его потомок B с тем же сокетом дописывает команду. Ждём NOT_A_SESSION."""
    r, w = os.pipe()
    a = os.fork()
    if a == 0:
        try:
            os.close(r)
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(SOCK)
            if os.fork() == 0:
                time.sleep(2)
                b = json.dumps({'kind': 'HEARTBEAT', 'args': {}})
                env = {'v': 1, 'lease_id': LEASE, 'nonce': os.urandom(32).hex(),
                       'sha256': hashlib.sha256(b.encode()).hexdigest(), 'body': b}
                s.settimeout(15)
                s.sendall((json.dumps(env) + '\n').encode())
                data = s.recv(4096)
                try:
                    res = json.loads(data)['result']
                except (ValueError, KeyError):
                    res = 'NO_ANSWER'
                os.write(w, res.encode('ascii', 'replace'))
                os._exit(0)
            time.sleep(0.5)
        finally:
            os._exit(0)
    os.close(w)
    os.waitpid(a, 0)
    out = b''
    while True:
        chunk = os.read(r, 256)
        if not chunk:
            break
        out += chunk
    os.close(r)
    return out.decode('ascii', 'replace') or 'NO_ANSWER'


def tcp(host, port):
    try:
        with socket.create_connection((host, port), timeout=5):
            return 'OPEN'
    except OSError as e:
        return 'DENIED_' + (os.strerror(e.errno).replace(' ', '_') if e.errno else type(e).__name__)


def dns_udp(server):
    q = struct.pack('>HHHHHH', 0x5a5a, 0x0100, 1, 0, 0, 0) + b'\x07example\x03com\x00' + struct.pack('>HH', 1, 1)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(3)
    try:
        s.sendto(q, (server, 53))
        s.recvfrom(512)
        return 'OPEN'
    except OSError as e:
        return 'DENIED_' + (os.strerror(e.errno).replace(' ', '_') if e.errno else type(e).__name__)
    finally:
        s.close()


def resolve(name):
    try:
        socket.getaddrinfo(name, 443)
        return 'OPEN'
    except OSError as e:
        return 'DENIED_' + type(e).__name__


def unix(path):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(3)
    try:
        s.connect(path)
        return 'OPEN'
    except OSError as e:
        return 'DENIED_' + (os.strerror(e.errno).replace(' ', '_') if e.errno else type(e).__name__)
    finally:
        s.close()


def proxy(line):
    try:
        with socket.create_connection(PROXY, timeout=15) as s:
            s.sendall(line.encode('ascii') + b'\r\n\r\n')
            data = s.recv(200)
        return data.split(b' ', 2)[1].decode('ascii') if data.startswith(b'HTTP/1.') else 'BAD_ANSWER'
    except OSError as e:
        return 'ERROR_' + type(e).__name__


def main():
    print(f'EGRESS_PROBE_START lease={LEASE} uid={os.getuid()}', flush=True)
    hb = {'kind': 'HEARTBEAT', 'args': {}}
    n1 = os.urandom(32).hex()
    first = 'NO_TRY'
    for _ in range(60):  # ждать отметки «работает» (её ставит CI за ядро)
        first = gate(hb, nonce=n1)
        if first != 'SESSION_NOT_RUNNING':
            break
        time.sleep(1)
    out('gate_first', first)
    out('gate_replay', gate(hb, nonce=n1))
    out('gate_bad_sha', gate(hb, sha='0' * 64))
    out('gate_other_lease', gate(hb, lease_id=OTHER))
    out('gate_dup_keys', gate('{"kind":"HEARTBEAT","kind":"PROGRESS","args":{}}'))
    out('gate_unknown_kind', gate({'kind': 'RUN_SQL', 'args': {}}))
    out('gate_extra_arg', gate({'kind': 'PROGRESS', 'args': {'text': 'x', 'sql': 'y'}}))
    out('gate_extra_field', gate(hb, extra={'sql': 'SELECT 1'}))
    out('gate_not_json', gate_raw(b'SELECT 1;\n'))
    out('gate_first_exited', gate_after_exit())
    out('gate_sql_text', gate({'kind': 'PROGRESS', 'args': {'text': "x'); DROP TABLE bem_control.gate_command; --"}}))
    out('net_direct_https', tcp('1.1.1.1', 443))
    out('net_dns_local_udp', dns_udp('127.0.0.53'))
    out('net_dns_public_udp', dns_udp('8.8.8.8'))
    out('net_dns_local_tcp', tcp('127.0.0.53', 53))
    out('net_ipv6_direct', tcp('2606:4700:4700::1111', 443))
    out('net_ipv6_loopback', tcp('::1', 22))
    out('net_resolve_name', resolve('example.com'))
    out('net_db_tcp', tcp('127.0.0.1', 5432))
    out('net_db_socket', unix('/run/postgresql/.s.PGSQL.5432'))
    out('net_dbus', unix('/run/dbus/system_bus_socket'))
    out('net_resolved_varlink', unix('/run/systemd/resolve/io.systemd.Resolve'))
    out('proxy_allowed', proxy('CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443'))
    out('proxy_github', proxy('CONNECT github.com:443 HTTP/1.1\r\nHost: github.com:443'))
    out('proxy_github_api', proxy('CONNECT api.github.com:443 HTTP/1.1\r\nHost: api.github.com:443'))
    out('proxy_github_raw', proxy('CONNECT raw.githubusercontent.com:443 HTTP/1.1\r\nHost: raw.githubusercontent.com:443'))
    out('proxy_ip_literal', proxy('CONNECT 1.1.1.1:443 HTTP/1.1\r\nHost: 1.1.1.1:443'))
    out('proxy_plain_get', proxy('GET http://example.com/ HTTP/1.1\r\nHost: example.com'))
    out('proxy_other_port', proxy('CONNECT example.com:80 HTTP/1.1\r\nHost: example.com:80'))
    print('EGRESS_PROBE_DONE', flush=True)
    time.sleep(1800)


if __name__ == '__main__':
    main()
