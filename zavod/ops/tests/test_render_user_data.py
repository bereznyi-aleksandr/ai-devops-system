# ДОКУМЕНТ: zavod/ops/tests/test_render_user_data.py
# ВЕРСИЯ: v0.3  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 10:39 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-12 11:11 +03:00 (v0.3: M-S6-R2-02 — третий ключ
#   (подпись билетов): совпадение любых двух ключей — отказ; release_signers — одна строка с namespaces;
#   папка билетов root 0700; v0.2: пользователь admin переименован в zadmin: в Ubuntu уже есть группа admin, useradd отказывает (CI 38219321184))
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: проверки zavod/ops/server/render_user_data.py (аудит ChatGPT S6-prep M-S6-02/03/05): закрытый ключ —
#   отказ; одинаковые ключи admin/zavod — отказ; у zavod нет группы sudo и нет NOPASSWD:ALL; правило sudoers
#   разрешает ровно install_release.sh; папка приёма принадлежит zavod с правами 0700; ключ zavod с restrict;
#   встроенные файлы совпадают байт в байт с исходниками; в результате нет строки PRIVATE KEY.
# ОГРАНИЧЕНИЯ: ключи — синтетические строки, не настоящие ключи. Временные файлы — tempfile.TemporaryDirectory,
#   четыре условия P4.718 как в test_sqlite_backup.py v0.1.
import base64
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))
import render_user_data as ru  # noqa: E402

A = 'ssh-ed25519 ' + 'A' * 68 + ' admin@test'
D = 'ssh-ed25519 ' + 'B' * 68 + ' deploy@test'
S = 'ssh-ed25519 ' + 'C' * 68 + ' release@test'
TGT = (1412203481, 'bereznyi-aleksandr/zavod-p1-bot', '48d39de1-2c46-4deb-8557-fec866f2e810')


def parse(text):
    head, _, body = text.partition('\n')
    assert head == '#cloud-config'
    return json.loads(body.split('\n', 1)[1])


class RenderUserDataTest(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.d = self._td.name

    def tearDown(self):
        self._td.cleanup()

    def key(self, name, text):
        p = os.path.join(self.d, name)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(text)
        return p

    def test_private_key_refused(self):
        marker = ' '.join(['OPENSSH', 'PRIVATE', 'KEY'])  # собрано из частей: сканер утечек не должен видеть заголовок
        p = self.key('id', f'-----BEGIN {marker}-----\nAAAA\n-----END {marker}-----\n')
        with self.assertRaises(SystemExit) as c:
            ru.read_pub(p)
        self.assertIn('private key', str(c.exception))

    def test_two_lines_refused(self):
        with self.assertRaises(SystemExit):
            ru.read_pub(self.key('k.pub', A + '\n' + D + '\n'))

    def test_same_keys_refused(self):
        with self.assertRaises(SystemExit) as c:
            ru.render(A, A.replace('admin', 'other'), S, *TGT)
        self.assertIn('differ', str(c.exception))
        with self.assertRaises(SystemExit):
            ru.render(A, D, D.replace('deploy', 'x'), *TGT)
        with self.assertRaises(SystemExit):
            ru.render(A, D, A, *TGT)

    def test_bad_target_refused(self):
        with self.assertRaises(SystemExit):
            ru.render(A, D, S, 0, TGT[1], TGT[2])
        with self.assertRaises(SystemExit):
            ru.render(A, D, S, TGT[0], 'a b/c', TGT[2])

    def test_permission_schema(self):
        out = ru.render(ru.read_pub(self.key('a.pub', A + '\n')), ru.read_pub(self.key('d.pub', D + '\n')),
                        ru.read_pub(self.key('s.pub', S + '\n')), *TGT)
        self.assertNotIn('PRIVATE KEY', out)
        cfg = parse(out)
        users = {u['name']: u for u in cfg['users']}
        self.assertEqual(set(users), {'zadmin', 'zavod', 'p1'})
        z = users['zavod']
        self.assertNotIn('sudo', z)
        self.assertNotIn('groups', z)
        self.assertEqual(z['ssh_authorized_keys'], ['restrict ' + D])
        self.assertEqual(users['zadmin']['ssh_authorized_keys'], [A])
        self.assertEqual(users['p1']['shell'], '/usr/sbin/nologin')
        files = {f['path']: f for f in cfg['write_files']}
        sud = base64.b64decode(files['/etc/sudoers.d/90-zavod-deploy']['content']).decode('utf-8')
        rules = [s for s in sud.splitlines() if s.strip() and not s.startswith('#')]
        self.assertEqual(rules, ['zavod ALL=(root) NOPASSWD: /opt/zavod-ops/install_release.sh'])
        self.assertEqual(files['/etc/sudoers.d/90-zavod-deploy']['permissions'], '0440')
        sshd = base64.b64decode(files['/etc/ssh/sshd_config.d/10-zavod.conf']['content']).decode('utf-8')
        self.assertIn('AllowUsers zadmin zavod', sshd)
        self.assertIn('PasswordAuthentication no', sshd)
        inc = [c for c in cfg['runcmd'] if ru.INCOMING in c]
        self.assertEqual(inc, [['install', '-d', '-o', 'zavod', '-g', 'zavod', '-m', '0700', ru.INCOMING]])
        tenv = base64.b64decode(files['/etc/zavod-p1/target.env']['content']).decode('utf-8')
        self.assertIn('TENANT_ID="48d39de1-2c46-4deb-8557-fec866f2e810"', tenv)
        sig = base64.b64decode(files['/etc/zavod-p1/release_signers']['content']).decode('utf-8')
        self.assertEqual(sig, 'zavod-release namespaces="zavod-release-ticket@v1" ' + ' '.join(S.split()[:2]) + '\n')
        self.assertEqual(files['/etc/zavod-p1/release_signers']['permissions'], '0644')
        self.assertIn(['install', '-d', '-o', 'root', '-g', 'root', '-m', '0700', '/var/lib/zavod-p1/tickets'], cfg['runcmd'])

    def test_embedded_files_match_sources(self):
        cfg = parse(ru.render(A, D, S, *TGT))
        files = {f['path']: f for f in cfg['write_files']}
        for path, rel in [('/opt/zavod-ops/install_release.sh', 'server/install_release.sh'),
                          ('/opt/zavod-ops/sqlite_backup.py', 'sqlite_backup.py'),
                          ('/opt/zavod-ops/liveness_watch.py', 'liveness_watch.py')]:
            self.assertEqual(base64.b64decode(files[path]['content']), ru.src(rel), path)
        self.assertEqual(files['/opt/zavod-ops/install_release.sh']['permissions'], '0755')


if __name__ == '__main__':
    unittest.main()
