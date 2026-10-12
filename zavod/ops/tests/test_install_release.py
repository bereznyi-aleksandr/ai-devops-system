# ДОКУМЕНТ: zavod/ops/tests/test_install_release.py
# ВЕРСИЯ: v0.2  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 08:40 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-12 10:32 +03:00 (v0.2: M-S6-02 —
#   файл вне папки приёма и ссылка в папке приёма — отказ BAD_INPUT_PATH до распаковки)
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: проверки zavod/ops/server/install_release.sh (E6-2, вторая линия сверки на сервере): точный выпуск
#   ставится и переключает current; повтор — already_present без изменений; подмена байта архива, чужой
#   repo_id/репозиторий, чужой tenant, плохой head_sha — отказ до распаковки; вторая версия не стирает первую.
# ОГРАНИЧЕНИЯ: только Linux (bash, ln -sfn, mv -T); на Windows пропускается. Перезапуск службы заменён записью
#   в файл (RESTART). Временные папки — tempfile.TemporaryDirectory, четыре условия P4.718 как в
#   test_sqlite_backup.py v0.1.
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
import hashlib

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'server', 'install_release.sh')
TARGET = {'REPO_ID': '1412203481', 'REPO_FULL_NAME': 'bereznyi-aleksandr/zavod-p1-bot',
          'TENANT_ID': '48d39de1-2c46-4deb-8557-fec866f2e810'}


@unittest.skipIf(os.name == 'nt', 'install_release.sh runs on the Linux server')
class InstallReleaseTest(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.d = self._td.name
        self.root = os.path.join(self.d, 'opt')
        os.makedirs(os.path.join(self.root, 'releases'))
        self.env = os.path.join(self.d, 'target.env')
        with open(self.env, 'w') as f:
            f.write(''.join(f'{k}="{v}"\n' for k, v in TARGET.items()))

    def tearDown(self):
        self._td.cleanup()

    def artifact(self, name, text):
        p = os.path.join(self.d, name)
        with tarfile.open(p, 'w') as t:
            data = text.encode('utf-8')
            ti = tarfile.TarInfo('bot/__main__.py')
            ti.size = len(data)
            t.addfile(ti, io.BytesIO(data))
        return p, hashlib.sha256(open(p, 'rb').read()).hexdigest()

    def manifest(self, name, sha, head, **over):
        m = {'artifact_sha256': sha, 'head_sha': head, 'repo_id': int(TARGET['REPO_ID']),
             'repo_full_name': TARGET['REPO_FULL_NAME'], 'tenant_id': TARGET['TENANT_ID']}
        m.update(over)
        p = os.path.join(self.d, name)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump({'manifest': m}, f)
        return p

    def run_install(self, mp, ap):
        env = dict(os.environ, ROOT=self.root, TARGET_ENV=self.env, SERVICE='zavod-p1',
                   JOURNAL=os.path.join(self.d, 'install.jsonl'), RESTART='true', INCOMING=self.d)
        return subprocess.run(['bash', SCRIPT, mp, ap], capture_output=True, text=True, env=env)

    def test_exact_installs_then_repeat_is_noop_then_second_keeps_first(self):
        h1, h2 = 'a' * 40, 'b' * 40
        a1, s1 = self.artifact('a1.tar', 'print(1)\n')
        r = self.run_install(self.manifest('m1.json', s1, h1), a1)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('INSTALL_OK state=installed', r.stdout)
        cur = os.path.join(self.root, 'current')
        self.assertEqual(os.path.realpath(cur), os.path.realpath(os.path.join(self.root, 'releases', h1)))
        r = self.run_install(self.manifest('m1.json', s1, h1), a1)
        self.assertIn('INSTALL_OK state=already_present', r.stdout)
        a2, s2 = self.artifact('a2.tar', 'print(2)\n')
        r = self.run_install(self.manifest('m2.json', s2, h2), a2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(os.path.realpath(cur), os.path.realpath(os.path.join(self.root, 'releases', h2)))
        self.assertTrue(os.path.isfile(os.path.join(self.root, 'releases', h1, 'bot', '__main__.py')))
        with open(os.path.join(self.d, 'install.jsonl')) as f:
            states = [json.loads(s)['state'] for s in f]
        self.assertEqual(states, ['installed', 'already_present', 'installed'])

    def refused(self, mp, ap):
        r = self.run_install(mp, ap)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertEqual(os.listdir(os.path.join(self.root, 'releases')), [])
        self.assertFalse(os.path.lexists(os.path.join(self.root, 'current')))
        return r.stdout.strip()

    def test_tampered_byte(self):
        a, s = self.artifact('a.tar', 'print(1)\n')
        mp = self.manifest('m.json', s, 'c' * 40)
        with open(a, 'r+b') as f:
            f.seek(600)
            b = f.read(1)
            f.seek(600)
            f.write(bytes([b[0] ^ 1]))
        self.assertEqual(self.refused(mp, a), 'INSTALL_REFUSED code=ARTIFACT_MISMATCH')

    def test_foreign_repo(self):
        a, s = self.artifact('a.tar', 'x\n')
        self.assertEqual(self.refused(self.manifest('m.json', s, 'c' * 40, repo_full_name='someone/other'), a),
                         'INSTALL_REFUSED code=TARGET_MISMATCH')
        self.assertEqual(self.refused(self.manifest('m2.json', s, 'c' * 40, repo_id=1), a),
                         'INSTALL_REFUSED code=TARGET_MISMATCH')

    def test_foreign_tenant(self):
        a, s = self.artifact('a.tar', 'x\n')
        self.assertEqual(self.refused(self.manifest('m.json', s, 'c' * 40, tenant_id='00000000-0000-0000-0000-000000000000'), a),
                         'INSTALL_REFUSED code=TENANT_MISMATCH')

    def test_input_outside_incoming_or_symlink(self):
        a, s = self.artifact('a.tar', 'x\n')
        mp = self.manifest('m.json', s, 'c' * 40)
        other = os.path.join(self.d, 'other')
        os.makedirs(other)
        a2 = os.path.join(other, 'a.tar')
        with open(a, 'rb') as f, open(a2, 'wb') as g:
            g.write(f.read())
        self.assertEqual(self.refused(mp, a2), 'INSTALL_REFUSED code=BAD_INPUT_PATH')
        link = os.path.join(self.d, 'link.tar')
        os.symlink(a, link)
        self.assertEqual(self.refused(mp, link), 'INSTALL_REFUSED code=BAD_INPUT_PATH')
        self.assertEqual(self.refused(mp, os.path.join(other, '..', 'a.tar')), 'INSTALL_REFUSED code=BAD_INPUT_PATH')

    def test_bad_head(self):
        a, s = self.artifact('a.tar', 'x\n')
        self.assertEqual(self.refused(self.manifest('m.json', s, '../../etc'), a), 'INSTALL_REFUSED code=BAD_HEAD')


if __name__ == '__main__':
    unittest.main()
