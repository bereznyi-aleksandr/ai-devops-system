# ДОКУМЕНТ: zavod/ops/tests/test_starter.py
# ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 15:05 +03:00
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: аудит ChatGPT S6-prep R8, критерии R9-2 и R9-3 — стартер сверяет ПОЛНЫЕ SHA-256 user-data и программы
#   применения; подмена любого из двух файлов после проверки аудитора (в том числе с сохранёнными отпечатками во 2-й
#   строке) — отказ sha256sum до запуска применения. Боевой запуск от root — в CI (zavod-kernel.yml), здесь — без root:
#   при верных суммах доходит до apply_user_data.py, который отвечает «REFUSED: run as root».
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, '..', 'server')
sys.path.insert(0, SERVER)
import render_starter as rs  # noqa: E402
import render_user_data as ru  # noqa: E402


def ed(fill, comment):
    raw = len(b'ssh-ed25519').to_bytes(4, 'big') + b'ssh-ed25519' + (32).to_bytes(4, 'big') + bytes([fill]) * 32
    return 'ssh-ed25519 ' + base64.b64encode(raw).decode('ascii') + ' ' + comment


A, D, S = ed(1, 'admin@test'), ed(2, 'deploy@test'), ed(3, 'release@test')
TGT = (1412203481, 'bereznyi-aleksandr/zavod-p1-bot', '48d39de1-2c46-4deb-8557-fec866f2e810')
GOOD = ru.render(A, D, S, *TGT, release_fp=ru.fingerprint(S))
COMMIT = '0' * 39 + '1'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def forged_same_line2():
    # подделка с СОХРАНЁННОЙ 2-й строкой (оба отпечатка верные) и добавленной службой от root
    head = GOOD.split('\n', 2)
    cfg = json.loads(head[2])
    cfg['write_files'].append(ru.wf('/etc/systemd/system/x.service', '[Service]\nExecStart=/bin/sh -c id\n', '0644'))
    cfg['runcmd'].append(['systemctl', 'enable', '--now', 'x.service'])
    return head[0] + '\n' + head[1] + '\n' + json.dumps(cfg, ensure_ascii=False, indent=1) + '\n'


class StarterTextTest(unittest.TestCase):
    def test_full_sums_and_commit(self):
        a = sha(b'apply')
        t = rs.starter(COMMIT, sha(GOOD.encode()), a)
        self.assertIn(f"B='https://raw.githubusercontent.com/bereznyi-aleksandr/ai-devops-system/{COMMIT}/zavod/ops'", t)
        self.assertIn(sha(GOOD.encode()) + ' user-data.yaml', t)
        self.assertIn(a + ' apply_user_data.py', t)
        self.assertIn('sha256sum -c --strict -', t)
        self.assertIn("--proto '=https'", t)
        self.assertTrue(t.startswith('#!/bin/sh\n'))
        self.assertEqual(t, rs.starter(COMMIT, sha(GOOD.encode()), a))

    def test_refuses_short_sums_and_bad_commit_l_s6_r8_01(self):
        good = sha(b'x')
        for c, u, a in [(COMMIT, good[:16], good), (COMMIT, good, good[:16]), ('main', good, good),
                        (COMMIT[:39], good, good), (COMMIT, good.upper(), good)]:
            with self.assertRaises(SystemExit):
                rs.starter(c, u, a)
        with self.assertRaises(SystemExit):
            rs.starter(COMMIT, good, good, base="x'; id; '")


@unittest.skipIf(os.name == 'nt', 'POSIX sh, curl file:// and sha256sum — Linux (CI)')
class StarterRunTest(unittest.TestCase):
    def run_starter(self, ud, apply_bytes, pinned_ud, pinned_apply):
        d = tempfile.mkdtemp(prefix='zavod-starter-')
        os.makedirs(os.path.join(d, 'raw', 'p1'))
        os.makedirs(os.path.join(d, 'raw', 'server'))
        with open(os.path.join(d, 'raw', 'p1', 'user-data.yaml'), 'w', encoding='utf-8', newline='\n') as f:
            f.write(ud)
        with open(os.path.join(d, 'raw', 'server', 'apply_user_data.py'), 'wb') as f:
            f.write(apply_bytes)
        text = rs.starter(COMMIT, pinned_ud, pinned_apply, base='file://' + os.path.join(d, 'raw'), proto='=file')
        p = os.path.join(d, 'starter.sh')
        with open(p, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        return subprocess.run(['sh', p], capture_output=True, text=True, encoding='utf-8', errors='replace')

    def setUp(self):
        with open(os.path.join(SERVER, 'apply_user_data.py'), 'rb') as f:
            self.apply = f.read()
        self.pin_ud, self.pin_apply = sha(GOOD.encode('utf-8')), sha(self.apply)

    def test_audited_files_reach_apply(self):
        r = self.run_starter(GOOD, self.apply, self.pin_ud, self.pin_apply)
        out = r.stdout + r.stderr
        self.assertIn('user-data.yaml: OK', out)
        self.assertIn('apply_user_data.py: OK', out)
        if os.geteuid() != 0:
            self.assertEqual(r.returncode, 2, out)
            self.assertIn('REFUSED: run as root', out)

    def test_substituted_user_data_refused_before_apply_r9_2(self):
        bad = forged_same_line2()
        self.assertEqual(bad.split('\n')[1], GOOD.split('\n')[1])
        r = self.run_starter(bad, self.apply, self.pin_ud, self.pin_apply)
        out = r.stdout + r.stderr
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('FAILED', out)
        self.assertNotIn('REFUSED: run as root', out)
        self.assertNotIn('"applied"', out)

    def test_substituted_apply_refused_before_apply(self):
        r = self.run_starter(GOOD, self.apply + b'\nimport os\n', self.pin_ud, self.pin_apply)
        out = r.stdout + r.stderr
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('FAILED', out)
        self.assertNotIn('REFUSED: run as root', out)

    def test_apply_refuses_non_root(self):
        if os.geteuid() == 0:
            self.skipTest('runs as root')
        d = tempfile.mkdtemp(prefix='zavod-apply-')
        p = os.path.join(d, 'u.yaml')
        with open(p, 'w', encoding='utf-8', newline='\n') as f:
            f.write(GOOD)
        r = subprocess.run([sys.executable, '-I', os.path.join(SERVER, 'apply_user_data.py'), p],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn('REFUSED: run as root', r.stderr)


if __name__ == '__main__':
    unittest.main()
