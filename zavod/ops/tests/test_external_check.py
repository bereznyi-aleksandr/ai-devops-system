# ДОКУМЕНТ: zavod/ops/tests/test_external_check.py
# ВЕРСИЯ: v0.3  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 08:40 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-12 10:45 +03:00 (v0.3: пользователь admin переименован в zadmin: в Ubuntu уже есть группа admin, useradd отказывает (CI 38219321184);
#   v0.2: M-S6-01 — main сканирует все 65535 портов, открытый порт выше 1024 даёт FAIL; пользователи zadmin, zavod, root)
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: проверки zavod/ops/external_check.py (E6-1): сканер видит открытый порт и не видит закрытый;
#   при ZAVOD_OPS_SSHD=1 (CI с sshd на 127.0.0.1 и настройками 10-zavod.conf) вход по паролю для zavod и root
#   отклонён, сервер предлагает только publickey.
# ОГРАНИЧЕНИЯ: сканирует только 127.0.0.1. Ключей и паролей не использует.
import os
import socket
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import external_check as ec  # noqa: E402


class ScanTest(unittest.TestCase):
    def test_open_and_closed(self):
        srv = socket.socket()
        srv.bind(('127.0.0.1', 0))
        srv.listen(1)
        p_open = srv.getsockname()[1]
        tmp = socket.socket()
        tmp.bind(('127.0.0.1', 0))
        p_closed = tmp.getsockname()[1]
        tmp.close()
        try:
            self.assertEqual(ec.open_ports('127.0.0.1', [p_open, p_closed], timeout=0.5), [p_open])
        finally:
            srv.close()

    def test_main_scans_all_ports_and_high_port_fails(self):
        seen = {}
        def fake_open(host, ports, timeout):
            seen['n'] = len(ports)
            seen['max'] = max(ports)
            return [22, 49152]
        def fake_pw(host, user, port=22):
            return {'user': user, 'rc': 255, 'methods': 'publickey', 'refused': True}
        o_open, o_pw = ec.open_ports, ec.password_refused
        ec.open_ports, ec.password_refused = fake_open, fake_pw
        try:
            self.assertEqual(ec.main(['203.0.113.10']), 1)
            self.assertEqual((seen['n'], seen['max']), (65535, 65535))
            ec.open_ports = lambda host, ports, timeout: [22]
            self.assertEqual(ec.main(['203.0.113.10']), 0)
        finally:
            ec.open_ports, ec.password_refused = o_open, o_pw


@unittest.skipUnless(os.environ.get('ZAVOD_OPS_SSHD') == '1', 'needs local sshd configured with 10-zavod.conf')
class PasswordLoginTest(unittest.TestCase):
    def test_password_refused_publickey_only(self):
        for user in ('zadmin', 'zavod', 'root'):
            r = ec.password_refused('127.0.0.1', user)
            self.assertTrue(r['refused'], r)
            self.assertEqual(r['methods'], 'publickey', r)


if __name__ == '__main__':
    unittest.main()
