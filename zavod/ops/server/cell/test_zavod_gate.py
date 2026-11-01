#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/cell/test_zavod_gate.py
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-02 00:07 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-02 00:07 +02:00
# ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
# НАЗНАЧЕНИЕ: проверка привратника zavod-gate без сервера (аудит M3310-R1B-01): нет дескриптора процесса
#   (SO_PEERPIDFD) — NOT_A_SESSION; дескриптор вышедшего процесса — не «жив»; процесс-собеседник вышел, пока шла
#   строка команды, — NOT_A_SESSION и база не вызывается; дескриптор закрывается в конце соединения.
#   Печатает ZAVOD_GATE_UNIT=PASS.
# ВЫЗОВ: python3 -I zavod/ops/server/cell/test_zavod_gate.py   (только Linux 6.5+: pidfd и SO_PEERPIDFD)
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import socket
import struct
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
_loader = importlib.machinery.SourceFileLoader('zavod_gate', os.path.join(HERE, 'zavod-gate'))
_spec = importlib.util.spec_from_loader('zavod_gate', _loader)
gate = importlib.util.module_from_spec(_spec)
_loader.exec_module(gate)

LEASE = '0123abcd-0000-4000-8000-00000000abcd'


def child_pidfd(seconds):
    pid = os.fork()
    if pid == 0:
        time.sleep(seconds)
        os._exit(0)
    return pid, os.pidfd_open(pid)


class NoPidfdConn:
    def getsockopt(self, level, opt, size):
        if opt == socket.SO_PEERCRED:
            return struct.pack('3i', os.getpid(), os.getuid(), os.getgid())
        raise OSError(92, 'Protocol not available')


class GateTest(unittest.TestCase):
    def test_no_pidfd_refused(self):
        with self.assertRaises(gate.Refuse) as e:
            gate.peer_session(NoPidfdConn())
        self.assertEqual(str(e.exception), 'NOT_A_SESSION')

    def test_alive_follows_process(self):
        pid, fd = child_pidfd(0.5)
        try:
            self.assertTrue(gate.alive(fd))
            os.waitpid(pid, 0)
            self.assertFalse(gate.alive(fd))
        finally:
            os.close(fd)

    def test_peer_exited_before_command_end(self):
        pid, fd = child_pidfd(0.2)
        closed = []
        calls = []
        real_close = os.close
        orig_peer, orig_db = gate.peer_session, gate.db
        gate.peer_session = lambda conn: (pid, os.getuid(), LEASE, fd)
        gate.db = lambda sql, env: calls.append(sql) or 'ACCEPTED 00000000-0000-4000-8000-000000000000'
        os.close = lambda f: (closed.append(f), real_close(f))[1]
        a, b = socket.socketpair()
        try:
            body = json.dumps({'kind': 'HEARTBEAT', 'args': {}})
            env = {'v': 1, 'lease_id': LEASE, 'nonce': os.urandom(32).hex(),
                   'sha256': hashlib.sha256(body.encode()).hexdigest(), 'body': body}
            line = (json.dumps(env) + '\n').encode()
            b.sendall(line[:10])
            os.waitpid(pid, 0)  # собеседник вышел посреди строки
            b.sendall(line[10:])
            gate.handle(a)
            answer = json.loads(b.recv(4096))
        finally:
            os.close = real_close
            gate.peer_session, gate.db = orig_peer, orig_db
            b.close()
        self.assertEqual(answer, {'result': 'NOT_A_SESSION'})
        self.assertEqual(calls, [])
        self.assertIn(fd, closed)


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    ok = r.wasSuccessful() and r.testsRun == 3 and not r.skipped
    print('ZAVOD_GATE_UNIT=' + ('PASS' if ok else 'FAIL'))
    sys.exit(0 if ok else 1)
