# ДОКУМЕНТ: zavod/ops/tests/test_verify_user_data.py
# ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 14:42 +03:00
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: аудит ChatGPT S6-prep R7, M-S6-R7-01, критерий R8-3 — подделки user-data (лишний ключ zadmin, ключ root,
#   широкий sudo, служба от root, лишняя команда, изменённый файл) ловятся до вставки: verify_user_data.py отвечает
#   USERDATA_MISMATCH, а сумма файла меняется, и Copy-ZavodUserData с кодом аудитора ничего не копирует.
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
sys.path.insert(0, os.path.join(HERE, '..', 'server'))
import render_user_data as ru  # noqa: E402
import verify_user_data as vu  # noqa: E402


def ed(fill, comment):
    raw = len(b'ssh-ed25519').to_bytes(4, 'big') + b'ssh-ed25519' + (32).to_bytes(4, 'big') + bytes([fill]) * 32
    return 'ssh-ed25519 ' + base64.b64encode(raw).decode('ascii') + ' ' + comment


A = ed(1, 'admin@test')
D = ed(2, 'deploy@test')
S = ed(3, 'release@test')
AGENT = ed(5, 'agent@test')
TGT = (1412203481, 'bereznyi-aleksandr/zavod-p1-bot', '48d39de1-2c46-4deb-8557-fec866f2e810')
GOOD = ru.render(A, D, S, *TGT, release_fp=ru.fingerprint(S))


def forge(change):
    head, body = GOOD.split('\n', 2)[:2], GOOD.split('\n', 2)[2]
    cfg = json.loads(body)
    change(cfg)
    return '\n'.join(head) + '\n' + json.dumps(cfg, ensure_ascii=False, indent=1) + '\n'


def wf(path, text, perm='0644'):
    return ru.wf(path, text, perm)


FORGERIES = {
    'extra zadmin key': lambda c: c['users'][0]['ssh_authorized_keys'].append(AGENT),
    'root authorized_keys': lambda c: c['write_files'].append(wf('/root/.ssh/authorized_keys', AGENT + '\n', '0600')),
    'zavod broad sudo (users)': lambda c: c['users'][1].update({'sudo': ['ALL=(ALL) NOPASSWD:ALL']}),
    'zavod broad sudo (sudoers.d)': lambda c: c['write_files'].append(
        wf('/etc/sudoers.d/91-x', 'zavod ALL=(ALL) NOPASSWD:ALL\n', '0440')),
    'root service': lambda c: (c['write_files'].append(wf('/etc/systemd/system/x.service',
                                                          '[Service]\nUser=root\nExecStart=/bin/sh -c id\n')),
                               c['runcmd'].append(['systemctl', 'enable', '--now', 'x.service'])),
    'extra runcmd': lambda c: c['runcmd'].append(['usermod', '-aG', 'sudo', 'zavod']),
    'changed installer': lambda c: c['write_files'][2].update(
        {'content': base64.b64encode(b'#!/bin/sh\nexit 0\n').decode('ascii')}),
}


class VerifyUserDataTest(unittest.TestCase):
    def test_clean_render_ok_with_inventory(self):
        out = vu.verify(GOOD.encode('utf-8'))
        self.assertTrue(out.startswith(f"USERDATA_OK sha256={hashlib.sha256(GOOD.encode('utf-8')).hexdigest()} "))
        self.assertIn(f'USER zadmin key {ru.fingerprint(A)}', out)
        self.assertIn(f'USER zavod key {ru.fingerprint(D)}', out)
        self.assertIn(f'RELEASE_SIGNER {ru.fingerprint(S)}', out)
        self.assertIn('FILE /etc/sudoers.d/90-zavod-deploy root:root 0440', out)
        self.assertEqual(sum(1 for line in out.split('\n') if line.startswith('FILE ')), 10)

    def test_forgeries_detected_r8_3(self):
        for name, change in FORGERIES.items():
            with self.subTest(name):
                bad = forge(change).encode('utf-8')
                self.assertNotEqual(hashlib.sha256(bad).digest(), hashlib.sha256(GOOD.encode('utf-8')).digest())
                with self.assertRaises(vu.Mismatch):
                    vu.verify(bad)

    def test_byte_level_changes_detected(self):
        for bad in [GOOD.replace('\n', '\r\n'), GOOD + '\n', GOOD.replace('"disable_root": true', '"disable_root": false'),
                    GOOD.replace('#cloud-config', '#cloud-config ', 1), 'not user-data\n']:
            with self.subTest(bad[:30]):
                with self.assertRaises(vu.Mismatch):
                    vu.verify(bad.encode('utf-8'))

    def test_main_exit_codes(self):
        d = tempfile.mkdtemp(prefix='zavod-vud-')
        good, bad = os.path.join(d, 'good.yaml'), os.path.join(d, 'bad.yaml')
        with open(good, 'w', encoding='utf-8', newline='\n') as f:
            f.write(GOOD)
        with open(bad, 'w', encoding='utf-8', newline='\n') as f:
            f.write(forge(FORGERIES['extra zadmin key']))
        script = os.path.join(HERE, '..', 'server', 'verify_user_data.py')
        r = subprocess.run([sys.executable, '-I', script, good], capture_output=True, text=True, encoding='utf-8', errors='replace')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('USERDATA_OK', r.stdout)
        r = subprocess.run([sys.executable, '-I', script, bad], capture_output=True, text=True, encoding='utf-8', errors='replace')
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stdout.startswith('USERDATA_MISMATCH'))

    def test_copy_zavod_user_data_pins_audited_hash(self):
        ps = shutil.which('pwsh') or shutil.which('powershell')
        self.assertIsNotNone(ps, 'PowerShell is required for the operator function test')
        d = tempfile.mkdtemp(prefix='zavod-cud-')
        good, bad, clip = os.path.join(d, 'good.yaml'), os.path.join(d, 'bad.yaml'), os.path.join(d, 'clip.txt')
        with open(good, 'w', encoding='utf-8', newline='\n') as f:
            f.write(GOOD)
        with open(bad, 'w', encoding='utf-8', newline='\n') as f:
            f.write(forge(FORGERIES['root service']))
        code = hashlib.sha256(GOOD.encode('utf-8')).hexdigest()[:16]
        fn = os.path.join(HERE, '..', 'operator', 'copy_user_data.ps1.txt')

        def run(path, typed):
            cmd = ("function Set-Clipboard { param($Value) [System.IO.File]::WriteAllText('" + clip + "', $Value) }; "
                   ". ([scriptblock]::Create((Get-Content -Raw -Encoding UTF8 '" + fn + "'))); "
                   "Copy-ZavodUserData -Path '" + path + "'")
            return subprocess.run([ps, '-NoProfile', '-Command', cmd], input=typed + '\n', capture_output=True,
                                  text=True, encoding='utf-8', errors='replace')

        r = run(good, 'deadbeefdeadbeef')
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(os.path.exists(clip))
        r = run(bad, code)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(os.path.exists(clip))
        r = run(good, code.upper())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn(hashlib.sha256(GOOD.encode('utf-8')).hexdigest(), r.stdout)
        with open(clip, 'rb') as f:
            self.assertEqual(f.read(), GOOD.encode('utf-8'))


if __name__ == '__main__':
    unittest.main()
