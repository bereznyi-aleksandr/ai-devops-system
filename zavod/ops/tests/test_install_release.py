# ДОКУМЕНТ: zavod/ops/tests/test_install_release.py
# ВЕРСИЯ: v0.3  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 08:40 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-12 11:11 +03:00 (v0.3: аудит ChatGPT
#   S6-prep R2 — M-S6-R2-01: suid/uid 0, символьная и жёсткая ссылка, устройство, FIFO, абсолютный путь, «..»,
#   повтор имени — отказ BAD_ARTIFACT_CONTENT до появления выпуска, current не меняется; права в выпуске только
#   0644/0755. M-S6-R2-02: билет выпуска с подписью ssh-keygen -Y — без подписи, чужой ключ, чужое пространство
#   имён, подмена байта билета, поле билета ≠ манифест, просрочка, срок больше часа, старый билет после нового —
#   отказ; повтор того же билета — already_present. v0.2: M-S6-02 — файл вне папки приёма и ссылка — отказ)
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: проверки zavod/ops/server/install_release.sh (E6-2, вторая линия сверки на сервере).
# ОГРАНИЧЕНИЯ: только Linux (bash, flock, ssh-keygen -Y, ln -sfn, mv -T); на Windows пропускается. Перезапуск службы
#   заменён командой true. Ключ подписи — одноразовый, создаётся ssh-keygen в tempfile.TemporaryDirectory этого
#   теста (четыре условия P4.718 как в test_sqlite_backup.py v0.1) и никуда не выходит.
import hashlib
import io
import json
import os
import subprocess
import tarfile
import tempfile
import time
import unittest
import uuid

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'server', 'install_release.sh')
TARGET = {'REPO_ID': '1412203481', 'REPO_FULL_NAME': 'bereznyi-aleksandr/zavod-p1-bot',
          'TENANT_ID': '48d39de1-2c46-4deb-8557-fec866f2e810'}
NS = 'zavod-release-ticket@v1'
WORK_ITEM = '3f1c2b9e-7d4a-4c1e-9b8f-2a6d5e4c3b21'


def keygen(path):
    subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'test', '-f', path], check=True)
    with open(path + '.pub') as f:
        return f.read().strip()


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
        keys = os.path.join(self.d, 'keys')
        os.makedirs(keys)
        self.key = os.path.join(keys, 'release')
        self.other_key = os.path.join(keys, 'other')
        pub = keygen(self.key)
        keygen(self.other_key)
        self.signers = os.path.join(self.d, 'release_signers')
        with open(self.signers, 'w') as f:
            f.write(f'zavod-release namespaces="{NS}" {pub}\n')
        self.n = 0
        self.clock = int(time.time())

    def tearDown(self):
        self._td.cleanup()

    def name(self, stem):
        self.n += 1
        return os.path.join(self.d, f'{stem}_{self.n}')

    def tar_of(self, members):
        p = self.name('a') + '.tar'
        with tarfile.open(p, 'w', format=tarfile.PAX_FORMAT) as t:
            for ti, data in members:
                t.addfile(ti, io.BytesIO(data) if data is not None else None)
        return p, hashlib.sha256(open(p, 'rb').read()).hexdigest()

    def artifact(self, text, mode=0o644):
        data = text.encode('utf-8')
        ti = tarfile.TarInfo('bot/__main__.py')
        ti.size = len(data)
        ti.mode = mode
        return self.tar_of([(ti, data)])

    def manifest(self, sha, head, **over):
        m = {'artifact_sha256': sha, 'head_sha': head, 'repo_id': int(TARGET['REPO_ID']),
             'repo_full_name': TARGET['REPO_FULL_NAME'], 'tenant_id': TARGET['TENANT_ID'],
             'work_item_id': WORK_ITEM, 'manifest_sha256': hashlib.sha256(head.encode() + sha.encode()).hexdigest()}
        m.update(over)
        p = self.name('m') + '.json'
        with open(p, 'w', encoding='utf-8') as f:
            json.dump({'manifest': m}, f)
        return p, m

    def ticket(self, m, key=None, ns=NS, issued=None, ttl=900, tid=None, **over):
        self.clock += 10
        iss = self.clock if issued is None else issued
        t = {'v': 1, 'ticket_id': tid or str(uuid.uuid4()), 'issued_at': iss, 'expires_at': iss + ttl}
        for k in ('head_sha', 'artifact_sha256', 'manifest_sha256', 'repo_id', 'repo_full_name', 'tenant_id', 'work_item_id'):
            t[k] = m[k]
        t.update(over)
        p = self.name('t') + '.json'
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(t, f)
        subprocess.run(['ssh-keygen', '-Y', 'sign', '-q', '-n', ns, '-f', key or self.key, p], check=True,
                       capture_output=True)
        return p, p + '.sig'

    def release(self, text='print(1)\n', head='a' * 40, **over):
        a, s = self.artifact(text)
        mp, m = self.manifest(s, head, **over)
        tp, sp = self.ticket(m)
        return mp, a, tp, sp

    def run_install(self, mp, ap, tp, sp):
        env = dict(os.environ, ROOT=self.root, TARGET_ENV=self.env, SERVICE='zavod-p1',
                   JOURNAL=os.path.join(self.d, 'install.jsonl'), RESTART='true', INCOMING=self.d,
                   RELEASE_SIGNERS=self.signers, TICKETS=os.path.join(self.d, 'tickets'))
        return subprocess.run(['bash', SCRIPT, mp, ap, tp, sp], capture_output=True, text=True, env=env)

    def refused(self, *args):
        before = sorted(os.listdir(os.path.join(self.root, 'releases')))
        cur = os.path.realpath(os.path.join(self.root, 'current')) if os.path.lexists(os.path.join(self.root, 'current')) else None
        r = self.run_install(*args)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, 'releases'))), before)
        now = os.path.realpath(os.path.join(self.root, 'current')) if os.path.lexists(os.path.join(self.root, 'current')) else None
        self.assertEqual(now, cur)
        return r.stdout.strip()

    def test_exact_installs_then_repeat_is_noop_then_second_keeps_first(self):
        h1, h2 = 'a' * 40, 'b' * 40
        a1, s1 = self.artifact('print(1)\n', mode=0o775)
        mp1, m1 = self.manifest(s1, h1)
        t1 = self.ticket(m1)
        r = self.run_install(mp1, a1, *t1)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('INSTALL_OK state=installed', r.stdout)
        cur = os.path.join(self.root, 'current')
        self.assertEqual(os.path.realpath(cur), os.path.realpath(os.path.join(self.root, 'releases', h1)))
        main = os.path.join(self.root, 'releases', h1, 'bot', '__main__.py')
        self.assertEqual(os.stat(main).st_mode & 0o7777, 0o755)
        self.assertEqual(os.stat(os.path.dirname(main)).st_mode & 0o7777, 0o755)
        r = self.run_install(mp1, a1, *t1)
        self.assertIn('INSTALL_OK state=already_present', r.stdout, r.stdout + r.stderr)
        mp2, a2, *t2 = self.release('print(2)\n', h2)
        r = self.run_install(mp2, a2, *t2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(os.path.realpath(cur), os.path.realpath(os.path.join(self.root, 'releases', h2)))
        self.assertTrue(os.path.isfile(main))
        with open(os.path.join(self.d, 'install.jsonl')) as f:
            states = [json.loads(s)['state'] for s in f]
        self.assertEqual(states, ['installed', 'already_present', 'installed'])
        # старый билет после нового — откат подменой не проходит
        self.assertEqual(self.refused(mp1, a1, *t1), 'INSTALL_REFUSED code=TICKET_STALE')

    def test_tampered_byte(self):
        a, s = self.artifact('print(1)\n')
        mp, m = self.manifest(s, 'c' * 40)
        t = self.ticket(m)
        with open(a, 'r+b') as f:
            f.seek(600)
            b = f.read(1)
            f.seek(600)
            f.write(bytes([b[0] ^ 1]))
        self.assertEqual(self.refused(mp, a, *t), 'INSTALL_REFUSED code=ARTIFACT_MISMATCH')

    def test_foreign_repo_tenant_head(self):
        self.assertEqual(self.refused(*self.release(head='c' * 40, repo_full_name='someone/other')),
                         'INSTALL_REFUSED code=TARGET_MISMATCH')
        self.assertEqual(self.refused(*self.release(head='c' * 40, repo_id=1)), 'INSTALL_REFUSED code=TARGET_MISMATCH')
        self.assertEqual(self.refused(*self.release(head='c' * 40, tenant_id='00000000-0000-0000-0000-000000000000')),
                         'INSTALL_REFUSED code=TENANT_MISMATCH')
        self.assertEqual(self.refused(*self.release(head='../../etc')), 'INSTALL_REFUSED code=BAD_HEAD')

    def test_input_outside_incoming_or_symlink(self):
        mp, a, tp, sp = self.release(head='c' * 40)
        other = os.path.join(self.d, 'other')
        os.makedirs(other)
        a2 = os.path.join(other, 'a.tar')
        with open(a, 'rb') as f, open(a2, 'wb') as g:
            g.write(f.read())
        self.assertEqual(self.refused(mp, a2, tp, sp), 'INSTALL_REFUSED code=BAD_INPUT_PATH')
        link = os.path.join(self.d, 'link.tar')
        os.symlink(a, link)
        self.assertEqual(self.refused(mp, link, tp, sp), 'INSTALL_REFUSED code=BAD_INPUT_PATH')
        self.assertEqual(self.refused(mp, os.path.join(other, '..', os.path.basename(a)), tp, sp),
                         'INSTALL_REFUSED code=BAD_INPUT_PATH')

    def test_ticket_signature(self):
        a, s = self.artifact('x\n')
        mp, m = self.manifest(s, 'c' * 40)
        tp, sp = self.ticket(m, key=self.other_key)
        self.assertEqual(self.refused(mp, a, tp, sp), 'INSTALL_REFUSED code=TICKET_BAD_SIGNATURE')
        tp, sp = self.ticket(m, ns='file')
        self.assertEqual(self.refused(mp, a, tp, sp), 'INSTALL_REFUSED code=TICKET_BAD_SIGNATURE')
        tp, sp = self.ticket(m)
        with open(tp, 'r+b') as f:
            raw = f.read().replace(b'"v": 1', b'"v": 1 ')
            f.seek(0)
            f.write(raw)
        self.assertEqual(self.refused(mp, a, tp, sp), 'INSTALL_REFUSED code=TICKET_BAD_SIGNATURE')
        tp, _ = self.ticket(m)
        empty = self.name('empty') + '.sig'
        open(empty, 'w').close()
        self.assertEqual(self.refused(mp, a, tp, empty), 'INSTALL_REFUSED code=TICKET_BAD_SIGNATURE')

    def test_ticket_fields_and_time(self):
        a, s = self.artifact('x\n')
        mp, m = self.manifest(s, 'c' * 40)
        for k, v in (('head_sha', 'd' * 40), ('artifact_sha256', '0' * 64), ('manifest_sha256', '1' * 64),
                     ('repo_id', 7), ('tenant_id', str(uuid.uuid4())), ('work_item_id', str(uuid.uuid4()))):
            self.assertEqual(self.refused(mp, a, *self.ticket(m, **{k: v})), 'INSTALL_REFUSED code=TICKET_MISMATCH', k)
        now = int(time.time())
        self.assertEqual(self.refused(mp, a, *self.ticket(m, issued=now - 1000, ttl=900)), 'INSTALL_REFUSED code=TICKET_EXPIRED')
        self.assertEqual(self.refused(mp, a, *self.ticket(m, ttl=7200)), 'INSTALL_REFUSED code=TICKET_BAD_FORMAT')
        self.assertEqual(self.refused(mp, a, *self.ticket(m, issued=now + 3000)), 'INSTALL_REFUSED code=TICKET_BAD_FORMAT')
        self.assertEqual(self.refused(mp, a, *self.ticket(m, tid='not-a-uuid')), 'INSTALL_REFUSED code=TICKET_BAD_FORMAT')

    def hostile(self, members, code='BAD_ARTIFACT_CONTENT'):
        a, s = self.tar_of(members)
        mp, m = self.manifest(s, 'e' * 40)
        self.assertEqual(self.refused(mp, a, *self.ticket(m)), f'INSTALL_REFUSED code={code}')
        self.assertFalse(os.path.lexists(os.path.join(self.root, 'releases', 'e' * 40)))

    def reg(self, name, data=b'x', mode=0o644, uid=0):
        ti = tarfile.TarInfo(name)
        ti.size, ti.mode, ti.uid, ti.gid = len(data), mode, uid, 0
        return ti, data

    def special(self, name, kind, linkname=''):
        ti = tarfile.TarInfo(name)
        ti.type, ti.linkname = kind, linkname
        return ti, None

    def test_hostile_archives_refused(self):
        self.hostile([self.reg('bot/su', mode=0o4755)])
        self.hostile([self.reg('bot/sg', mode=0o2755)])
        self.hostile([self.reg('bot/st', mode=0o1755)])
        self.hostile([self.reg('bot/ok.py'), self.special('bot/link', tarfile.SYMTYPE, '/etc/shadow')])
        self.hostile([self.reg('bot/ok.py'), self.special('bot/hard', tarfile.LNKTYPE, 'bot/ok.py')])
        self.hostile([self.special('bot/dev', tarfile.CHRTYPE)])
        self.hostile([self.special('bot/blk', tarfile.BLKTYPE)])
        self.hostile([self.special('bot/fifo', tarfile.FIFOTYPE)])
        self.hostile([self.reg('/etc/cron.d/x')])
        self.hostile([self.reg('bot/../../x')])
        self.hostile([self.reg('./bot/x')])
        self.hostile([self.reg('bot/x'), self.reg('bot/x')])
        self.hostile([self.reg('bot'), self.reg('bot/x')])
        self.hostile([self.reg('.artifact_sha256')])
        self.hostile([self.reg('bot/a\nb')])
        self.assertFalse(os.path.lexists(os.path.join(self.root, 'current')))

    def test_root_owned_tar_is_installed_with_safe_modes(self):
        dti = tarfile.TarInfo('bot')
        dti.type, dti.mode, dti.uid = tarfile.DIRTYPE, 0o777, 0
        a, s = self.tar_of([(dti, None), self.reg('bot/__main__.py', b'print(1)\n', mode=0o666, uid=0),
                            self.reg('bot/run', b'#!/bin/sh\n', mode=0o777, uid=0)])
        mp, m = self.manifest(s, 'f' * 40)
        r = self.run_install(mp, a, *self.ticket(m))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rel = os.path.join(self.root, 'releases', 'f' * 40)
        me = os.geteuid()
        for p, mode in ((os.path.join(rel, 'bot'), 0o755), (os.path.join(rel, 'bot', '__main__.py'), 0o644),
                        (os.path.join(rel, 'bot', 'run'), 0o755), (os.path.join(rel, '.artifact_sha256'), 0o644)):
            st = os.lstat(p)
            self.assertEqual(st.st_mode & 0o7777, mode, p)
            self.assertEqual(st.st_uid, me, p)


if __name__ == '__main__':
    unittest.main()
