# ДОКУМЕНТ: zavod/ops/tests/test_zsign_phone.py
# ВЕРСИЯ: v0.2  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 16:19 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-12 16:55 +03:00 (v0.2: аудит ChatGPT
#   S6-prep R11A L-S6-R11-01 — билет в точном виде Завода (полный набор полей в порядке JSON.stringify); повтор,
#   лишнее и пропущенное поле, пробелы, другой порядок, не-ASCII и управляющие знаки, перевод строки, срок больше
#   часа — отказ без подписи; в выводе полный head и ссылка на коммит (M-S6-R11-01))
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: проверки zavod/ops/operator/zsign_phone.sh (аудит ChatGPT S6-prep R10, критерии R11-2, R11-3): подпись
#   билета на телефоне. Верный билет и верный код — подпись, которую принимает `ssh-keygen -Y verify` с
#   release_signers в том же виде, что на сервере, и которая не подходит к изменённому билету; неверный код,
#   просроченный билет, не билет, битая строка, нет ключа — отказ без подписи.
# ОГРАНИЧЕНИЯ: запускается там, где есть sh, base64, sha256sum и ssh-keygen с -Y (Linux CI, Termux); на Windows —
#   пропуск. Ключ тестовый без пароля. Временные файлы — tempfile.TemporaryDirectory (четыре условия P4.718 как в
#   test_sqlite_backup.py v0.1); временная папка самой программы — в TMPDIR внутри неё.
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, '..', 'operator', 'zsign_phone.sh')
NS = 'zavod-release-ticket@v1'
ARMOR = re.compile(r'-----BEGIN SSH SIGNATURE-----\n.*?\n-----END SSH SIGNATURE-----\n', re.S)


def ticket(expires_in=3600, issued_ago=0):
    now = int(time.time())
    t = {'v': 1, 'ticket_id': '7ec633bb-d4ab-4f99-997a-0c4fad9de08e', 'issued_at': now - issued_ago, 'expires_at': now + expires_in,
         'head_sha': 'a' * 40, 'artifact_sha256': 'b' * 64, 'manifest_sha256': 'c' * 64, 'repo_id': 1412203481,
         'repo_full_name': 'bereznyi-aleksandr/zavod-p1-bot', 'tenant_id': '48d39de1-2c46-4deb-8557-fec866f2e810',
         'work_item_id': '3f1c2b9e-7d4a-4c1e-9b8f-2a6d5e4c3b21'}
    return json.dumps(t, separators=(',', ':')).encode('utf-8')


@unittest.skipIf(os.name == 'nt' or not shutil.which('ssh-keygen') or not shutil.which('base64'), 'нужен sh и ssh-keygen Linux/Termux')
class ZsignPhoneTest(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.home = self._td.name
        os.makedirs(os.path.join(self.home, '.ssh'))
        os.makedirs(os.path.join(self.home, 'tmp'))
        self.key = os.path.join(self.home, '.ssh', 'zavod_release_sign')
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'zavod-release', '-f', self.key], check=True)
        with open(self.key + '.pub', encoding='utf-8') as f:
            pub = ' '.join(f.read().split()[:2])
        self.signers = os.path.join(self.home, 'release_signers')
        with open(self.signers, 'w', encoding='utf-8') as f:
            f.write(f'zavod-release namespaces="{NS}" {pub}\n')

    def tearDown(self):
        self._td.cleanup()

    def run_sign(self, b64, code):
        env = {'PATH': os.environ['PATH'], 'HOME': self.home, 'TMPDIR': os.path.join(self.home, 'tmp')}
        return subprocess.run(['sh', SCRIPT, b64], input=code + '\n', capture_output=True, text=True, env=env)

    def verify(self, data, armor):
        sig = os.path.join(self.home, 'check.sig')
        with open(sig, 'w', encoding='utf-8') as f:
            f.write(armor)
        return subprocess.run(['ssh-keygen', '-Y', 'verify', '-f', self.signers, '-I', 'zavod-release', '-n', NS, '-s', sig],
                              input=data, capture_output=True).returncode

    def test_signs_shown_bytes(self):
        t = ticket()
        h = hashlib.sha256(t).hexdigest()
        r = self.run_sign(base64.b64encode(t).decode('ascii'), h[:8])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('SHA-256 билета: ' + h, r.stdout)
        self.assertIn('head:        ' + 'a' * 40 + '\n', r.stdout)
        self.assertIn('https://github.com/bereznyi-aleksandr/zavod-p1-bot/commit/' + 'a' * 40 + '\n', r.stdout)
        m = ARMOR.search(r.stdout)
        self.assertIsNotNone(m, r.stdout)
        self.assertEqual(self.verify(t, m.group(0)), 0)
        self.assertNotEqual(self.verify(t.replace(b'"a', b'"c', 1), m.group(0)), 0)

    def test_refusals_without_signature(self):
        good = ticket()
        h = hashlib.sha256(good).hexdigest()
        old = ticket(expires_in=-30, issued_ago=120)
        cases = [
            (base64.b64encode(good).decode(), 'deadbeef', 5),
            (base64.b64encode(old).decode(), hashlib.sha256(old).hexdigest()[:8], 4),
            (base64.b64encode(b'hello world').decode(), h[:8], 3),
            ('!!!not-base64!!!', h[:8], 3),
        ]
        for b64, code, rc in cases:
            r = self.run_sign(b64, code)
            self.assertEqual(r.returncode, rc, (b64[:20], r.stdout, r.stderr))
            self.assertNotIn('BEGIN SSH SIGNATURE', r.stdout)
        os.rename(self.key, self.key + '.moved')
        r = self.run_sign(base64.b64encode(good).decode(), h[:8])
        self.assertEqual(r.returncode, 2)
        self.assertNotIn('BEGIN SSH SIGNATURE', r.stdout)

    def test_strict_ticket_form_l_s6_r11_01(self):
        good = ticket()
        bad = [
            good.replace(b'"v":1,', b'"v":1,"v":1,', 1),                                   # повтор поля
            good[:-1] + b',"extra":1}',                                                 # лишнее поле
            good.replace(b',"work_item_id":"3f1c2b9e-7d4a-4c1e-9b8f-2a6d5e4c3b21"', b''),  # пропущено поле
            json.dumps(json.loads(good)).encode(),                                      # пробелы
            json.dumps(dict(reversed(list(json.loads(good).items()))), separators=(',', ':')).encode(),  # порядок
            good.replace(b'bereznyi-aleksandr', 'bereznyі-aleksandr'.encode('utf-8')),  # не-ASCII (кириллица і)
            good.replace(b'bereznyi-aleksandr', b'bereznyi-\\u202ealeksandr'),          # управляющий знак в JSON
            good.replace(b'bereznyi-aleksandr', b'bereznyi\taleksandr'),
            good + b'\n',                                                                # перевод строки
            good.replace(b'"repo_id":1412203481', b'"repo_id":"1412203481"'),           # другой тип
        ]
        t = json.loads(good)
        t['expires_at'] = t['issued_at'] + 7200
        bad.append(json.dumps(t, separators=(',', ':')).encode())                       # срок больше часа
        for b in bad:
            r = self.run_sign(base64.b64encode(b).decode('ascii'), hashlib.sha256(b).hexdigest()[:8])
            self.assertEqual(r.returncode, 3, (b, r.stdout, r.stderr))
            self.assertNotIn('BEGIN SSH SIGNATURE', r.stdout)


if __name__ == '__main__':
    unittest.main()
