# ДОКУМЕНТ: zavod/ops/tests/test_render_user_data.py
# ВЕРСИЯ: v0.7  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 10:39 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-16 19:53 +03:00 (v0.7: M-R13-02 аудита
#   Codex — версия v0.7 видна в созданном cloud-config и в отчёте verify_user_data; пакет git. v0.6: R7 — во 2-й строке и отпечаток ключа
#   zadmin; ключ с опциями перед типом в render() — отказ; v0.5: R6 — синтетические ключи стали
#   настоящими по форме блоками ssh-ed25519; неканонический base64 (TR== вместо TQ==, лишние биты), битый блок,
#   хвост после ключа — отказ; вторая строка user-data несёт RELEASE_KEY_FINGERPRINT для сверки оператором; v0.4: M-S6-R5-01 — отпечаток оператора
#   обязателен: нет/не того вида/не совпал с .pub (подменённый ключ при отпечатке оператора) — отказ до вывода
#   user-data, в том числе через командную строку; ключ подписи не ed25519 — отказ; отпечаток совпадает с
#   ssh-keygen -lf на настоящем ключе; v0.3: M-S6-R2-02 — третий ключ
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
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))
import render_user_data as ru  # noqa: E402
import verify_user_data as vu  # noqa: E402

def ed(fill, comment):
    raw = len(b'ssh-ed25519').to_bytes(4, 'big') + b'ssh-ed25519' + (32).to_bytes(4, 'big') + bytes([fill]) * 32
    return 'ssh-ed25519 ' + base64.b64encode(raw).decode('ascii') + ' ' + comment


A = ed(1, 'admin@test')
D = ed(2, 'deploy@test')
S = ed(3, 'release@test')
TGT = (1412203481, 'bereznyi-aleksandr/zavod-p1-bot', '48d39de1-2c46-4deb-8557-fec866f2e810')
FS = ru.fingerprint(S)


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
            ru.render(A, A.replace('admin', 'other'), S, *TGT, release_fp=FS)
        self.assertIn('differ', str(c.exception))
        with self.assertRaises(SystemExit):
            ru.render(A, D, D.replace('deploy', 'x'), *TGT, release_fp=FS)
        with self.assertRaises(SystemExit):
            ru.render(A, D, A, *TGT, release_fp=FS)

    def test_bad_target_refused(self):
        with self.assertRaises(SystemExit):
            ru.render(A, D, S, 0, TGT[1], TGT[2], release_fp=FS)
        with self.assertRaises(SystemExit):
            ru.render(A, D, S, TGT[0], 'a b/c', TGT[2], release_fp=FS)

    def test_permission_schema(self):
        out = ru.render(ru.read_pub(self.key('a.pub', A + '\n')), ru.read_pub(self.key('d.pub', D + '\n')),
                        ru.read_pub(self.key('s.pub', S + '\n')), *TGT, release_fp=FS)
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

    def test_operator_fingerprint_required_m_s6_r5_01(self):
        with self.assertRaises(SystemExit) as c:
            ru.render(A, D, S, *TGT, release_fp=None)
        self.assertIn('fingerprint', str(c.exception))
        with self.assertRaises(SystemExit):
            ru.render(A, D, S, *TGT, release_fp=FS[7:])
        with self.assertRaises(TypeError):
            ru.render(A, D, S, *TGT)  # без отпечатка вызвать нельзя вовсе
        agent = ed(5, 'agent@test')
        with self.assertRaises(SystemExit) as c:
            ru.render(A, D, agent, *TGT, release_fp=FS)  # подменённый .pub при отпечатке оператора
        self.assertIn('does not match', str(c.exception))
        rsa = 'ssh-rsa ' + 'C' * 68 + ' release@test'
        with self.assertRaises(SystemExit) as c:
            ru.render(A, D, rsa, *TGT, release_fp=ru.fingerprint(rsa))
        self.assertIn('ed25519', str(c.exception))
        args = ['--admin-pubkey', self.key('a.pub', A), '--deploy-pubkey', self.key('d.pub', D),
                '--release-signer-pubkey', self.key('s.pub', agent), '--repo-id', str(TGT[0]), '--repo', TGT[1], '--tenant', TGT[2]]
        out = io.StringIO()
        for extra in ([], ['--release-signer-fingerprint', FS]):
            with self.assertRaises(SystemExit), redirect_stdout(out), redirect_stderr(io.StringIO()):
                ru.main(args + extra)
        self.assertEqual(out.getvalue(), '', 'при отказе user-data не выводится')

    @unittest.skipUnless(shutil.which('ssh-keygen'), 'нужен ssh-keygen')
    def test_fingerprint_matches_ssh_keygen(self):
        k = os.path.join(self.d, 'rk')
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'r', '-f', k], check=True)
        pub = ru.read_pub(k + '.pub')
        lf = subprocess.run(['ssh-keygen', '-lf', k + '.pub'], check=True, capture_output=True, text=True).stdout.split()[1]
        self.assertEqual(ru.fingerprint(pub), lf)
        self.assertIn('release_signers', ru.render(A, D, pub, *TGT, release_fp=lf))

    def test_strict_release_key_l_s6_r6_01(self):
        # настоящий блок ssh-ed25519 — 51 байт, base64 без «=»; неканоничность проверяем на записи с «==»
        b64 = base64.b64encode(base64.b64decode(S.split()[1]) + b'x').decode('ascii')
        self.assertTrue(b64.endswith('=='))
        # те же байты, иная (неканоническая) запись: меняем младшие «лишние» биты последнего значащего символа
        alpha = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
        body = b64.rstrip('=')
        pad = b64[len(body):]
        last = alpha[alpha.index(body[-1]) + 1]
        loose = 'ssh-ed25519 ' + body[:-1] + last + pad + ' release@test'
        self.assertEqual(base64.b64decode(loose.split()[1], validate=True), base64.b64decode(b64))
        for bad, why in [(loose, 'non-canonical'),
                         ('ssh-ed25519 ' + b64 + ' r', 'well-formed'),
                         ('ssh-ed25519 ' + base64.b64encode(base64.b64decode(S.split()[1])[:-1]).decode() + ' r', 'blob')]:
            with self.assertRaises(SystemExit) as c:
                ru.render(A, D, bad, *TGT, release_fp=FS)
            self.assertIn(why, str(c.exception))
        self.assertEqual(base64.b64decode('TR==', validate=True), base64.b64decode('TQ=='))
        with self.assertRaises(SystemExit):
            ru.key_blob('ssh-ed25519 TR==')

    def test_fingerprint_line_for_operator(self):
        out = ru.render(A, D, S, *TGT, release_fp=FS)
        second = out.split('\n')[1]
        self.assertTrue(second.startswith('# '))
        self.assertIn('RELEASE_KEY_FINGERPRINT ' + FS + ';', second)
        self.assertIn('ADMIN_KEY_FINGERPRINT ' + ru.fingerprint(A) + ' ', second)
        for bad in ['from="1.2.3.4" ' + A, A + '\nssh-ed25519 ' + S.split()[1]]:
            with self.assertRaises(SystemExit):
                ru.render(bad, D, S, *TGT, release_fp=FS)

    def test_embedded_files_match_sources(self):
        cfg = parse(ru.render(A, D, S, *TGT, release_fp=FS))
        files = {f['path']: f for f in cfg['write_files']}
        for path, rel in [('/opt/zavod-ops/install_release.sh', 'server/install_release.sh'),
                          ('/opt/zavod-ops/sqlite_backup.py', 'sqlite_backup.py'),
                          ('/opt/zavod-ops/liveness_watch.py', 'liveness_watch.py')]:
            self.assertEqual(base64.b64decode(files[path]['content']), ru.src(rel), path)
        self.assertEqual(files['/opt/zavod-ops/install_release.sh']['permissions'], '0755')

    def test_version_in_cloud_config_and_report_m_r13_02(self):
        out = ru.render(A, D, S, *TGT, release_fp=FS)
        self.assertEqual(ru.VERSION, 'v0.7')
        self.assertIn('# zavod/ops/server/render_user_data.py v0.7;', out.split('\n')[1])
        self.assertIn(' render=v0.7 ', vu.verify(out.encode('utf-8')).split('\n')[0] + ' ')
        self.assertIn('git', parse(out)['packages'])


if __name__ == '__main__':
    unittest.main()
