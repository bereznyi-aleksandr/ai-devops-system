# ДОКУМЕНТ: zavod/ops/tests/test_install_release.py
# ВЕРСИЯ: v0.8  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 08:40 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-16 20:19 +03:00 (v0.8: L-R15-01 аудита Codex —
#   помощники закрывают файлы (sha256_file, load_json): в журнале нет ResourceWarning. v0.7: M-R14-01 аудита Codex —
#   во временных репозиториях проверок запрещено фоновое обслуживание git (gc.auto=0, maintenance.auto=false). v0.6: M-R13-01 аудита Codex —
#   выпуск из 1200 файлов в 1600 папках ставится не больше чем за три запуска git hash-object. v0.5: L-S6-R12-01 —
#   три проверки git с SHA1DC: настоящий git сообщает SHA1_DC или ничего; git без SHA1DC — GIT_NO_SHA1DC; отказ или
#   ложный хеш git — SHA1_GUARD_FAILED. v0.4: аудит ChatGPT S6-prep R11A
#   M-S6-R11-01 — install_release.sh v0.4 сверяет архив с подписанным head по git-хешам: выпуски в проверках —
#   настоящие коммиты git (git archive + git cat-file commit), пятый аргумент — объект коммита. Новые проверки:
#   верная подпись и верные repo/head, но чужой архив, лишний файл, другой бит исполнения — ARTIFACT_NOT_FROM_HEAD;
#   объект другого коммита или пустой — COMMIT_NOT_HEAD; коммит с файлом .artifact_sha256 проходит сверку дерева, но
#   распаковка его не принимает (BAD_ARTIFACT_CONTENT); архив не из git с тем же деревом ставится. v0.3: аудит ChatGPT
#   S6-prep R2 — M-S6-R2-01: suid/uid 0, символьная и жёсткая ссылка, устройство, FIFO, абсолютный путь, «..»,
#   повтор имени — отказ BAD_ARTIFACT_CONTENT до появления выпуска, current не меняется; права в выпуске только
#   0644/0755. M-S6-R2-02: билет выпуска с подписью ssh-keygen -Y — без подписи, чужой ключ, чужое пространство
#   имён, подмена байта билета, поле билета ≠ манифест, просрочка, срок больше часа, старый билет после нового —
#   отказ; повтор того же билета — already_present. v0.2: M-S6-02 — файл вне папки приёма и ссылка — отказ)
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: проверки zavod/ops/server/install_release.sh (E6-2, вторая линия сверки на сервере).
# ОГРАНИЧЕНИЯ: только Linux (bash, flock, git, ssh-keygen -Y, ln -sfn, mv -T); на Windows пропускается. Перезапуск
#   службы заменён командой true. Ключ подписи — одноразовый, создаётся ssh-keygen в tempfile.TemporaryDirectory этого
#   теста; там же одноразовые git-репозитории (четыре условия P4.718 как в test_sqlite_backup.py v0.1); никуда не
#   выходит.
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


def sha256_file(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def load_json(path):
    with open(path) as f:
        return json.load(f)


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

    def git(self, repo, *a):
        return subprocess.run(['git', '-C', repo, '-c', 'core.autocrlf=false',
                               '-c', 'gc.auto=0', '-c', 'maintenance.auto=false',
                               '-c', 'user.name=zavod-test', '-c', 'user.email=t@zavod.invalid', *a],
                              check=True, capture_output=True).stdout

    def commit(self, files):
        """files: {путь: (байты, исполняемый)} → (head, путь архива git archive, его sha256, путь объекта коммита)"""
        repo = self.name('g')
        subprocess.run(['git', 'init', '-q', repo], check=True)
        for p, (data, ex) in files.items():
            full = os.path.join(repo, *p.split('/'))
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, 'wb') as f:
                f.write(data)
            os.chmod(full, 0o755 if ex else 0o644)
        self.git(repo, 'add', '-A')
        self.git(repo, 'commit', '-q', '-m', 'release')
        head = self.git(repo, 'rev-parse', 'HEAD').decode().strip()
        a = self.name('a') + '.tar'
        with open(a, 'wb') as f:
            f.write(self.git(repo, 'archive', '--format=tar', 'HEAD'))
        cp = self.name('c') + '.obj'
        with open(cp, 'wb') as f:
            f.write(self.git(repo, 'cat-file', 'commit', head))
        return head, a, sha256_file(a), cp

    def tar_of(self, members):
        p = self.name('a') + '.tar'
        with tarfile.open(p, 'w', format=tarfile.PAX_FORMAT) as t:
            for ti, data in members:
                t.addfile(ti, io.BytesIO(data) if data is not None else None)
        return p, sha256_file(p)

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

    def release(self, text='print(1)\n', head=None, ex=False, **over):
        h, a, s, cp = self.commit({'bot/__main__.py': (text.encode('utf-8'), ex)})
        mp, m = self.manifest(s, head or h, **over)
        tp, sp = self.ticket(m)
        return mp, a, tp, sp, cp

    def run_install(self, mp, ap, tp, sp, cp):
        env = dict(os.environ, ROOT=self.root, TARGET_ENV=self.env, SERVICE='zavod-p1',
                   JOURNAL=os.path.join(self.d, 'install.jsonl'), RESTART='true', INCOMING=self.d,
                   RELEASE_SIGNERS=self.signers, TICKETS=os.path.join(self.d, 'tickets'))
        if getattr(self, 'git_bin', None):
            env['GIT'] = self.git_bin
        return subprocess.run(['bash', SCRIPT, mp, ap, tp, sp, cp], capture_output=True, text=True, env=env)

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
        mp1, a1, tp1, sp1, cp1 = self.release('print(1)\n', ex=True)
        h1 = load_json(mp1)['manifest']['head_sha']
        r = self.run_install(mp1, a1, tp1, sp1, cp1)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('INSTALL_OK state=installed', r.stdout)
        cur = os.path.join(self.root, 'current')
        self.assertEqual(os.path.realpath(cur), os.path.realpath(os.path.join(self.root, 'releases', h1)))
        main = os.path.join(self.root, 'releases', h1, 'bot', '__main__.py')
        self.assertEqual(os.stat(main).st_mode & 0o7777, 0o755)
        self.assertEqual(os.stat(os.path.dirname(main)).st_mode & 0o7777, 0o755)
        r = self.run_install(mp1, a1, tp1, sp1, cp1)
        self.assertIn('INSTALL_OK state=already_present', r.stdout, r.stdout + r.stderr)
        mp2, a2, *rest2 = self.release('print(2)\n')
        h2 = load_json(mp2)['manifest']['head_sha']
        r = self.run_install(mp2, a2, *rest2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(os.path.realpath(cur), os.path.realpath(os.path.join(self.root, 'releases', h2)))
        self.assertTrue(os.path.isfile(main))
        with open(os.path.join(self.d, 'install.jsonl')) as f:
            states = [json.loads(s)['state'] for s in f]
        self.assertEqual(states, ['installed', 'already_present', 'installed'])
        # старый билет после нового — откат подменой не проходит
        self.assertEqual(self.refused(mp1, a1, tp1, sp1, cp1), 'INSTALL_REFUSED code=TICKET_STALE')

    def test_tampered_byte(self):
        mp, a, tp, sp, cp = self.release()
        with open(a, 'r+b') as f:
            f.seek(600)
            b = f.read(1)
            f.seek(600)
            f.write(bytes([b[0] ^ 1]))
        self.assertEqual(self.refused(mp, a, tp, sp, cp), 'INSTALL_REFUSED code=ARTIFACT_MISMATCH')

    def test_foreign_repo_tenant_head(self):
        self.assertEqual(self.refused(*self.release(repo_full_name='someone/other')), 'INSTALL_REFUSED code=TARGET_MISMATCH')
        self.assertEqual(self.refused(*self.release(repo_id=1)), 'INSTALL_REFUSED code=TARGET_MISMATCH')
        self.assertEqual(self.refused(*self.release(tenant_id='00000000-0000-0000-0000-000000000000')),
                         'INSTALL_REFUSED code=TENANT_MISMATCH')
        self.assertEqual(self.refused(*self.release(head='../../etc')), 'INSTALL_REFUSED code=BAD_HEAD')

    def test_input_outside_incoming_or_symlink(self):
        mp, a, tp, sp, cp = self.release()
        other = os.path.join(self.d, 'other')
        os.makedirs(other)
        a2 = os.path.join(other, 'a.tar')
        with open(a, 'rb') as f, open(a2, 'wb') as g:
            g.write(f.read())
        self.assertEqual(self.refused(mp, a2, tp, sp, cp), 'INSTALL_REFUSED code=BAD_INPUT_PATH')
        link = os.path.join(self.d, 'link.tar')
        os.symlink(a, link)
        self.assertEqual(self.refused(mp, link, tp, sp, cp), 'INSTALL_REFUSED code=BAD_INPUT_PATH')
        self.assertEqual(self.refused(mp, os.path.join(other, '..', os.path.basename(a)), tp, sp, cp),
                         'INSTALL_REFUSED code=BAD_INPUT_PATH')
        c2 = os.path.join(other, 'c.obj')
        with open(cp, 'rb') as f, open(c2, 'wb') as g:
            g.write(f.read())
        self.assertEqual(self.refused(mp, a, tp, sp, c2), 'INSTALL_REFUSED code=BAD_INPUT_PATH')

    def test_ticket_signature(self):
        h, a, s, cp = self.commit({'bot/x': (b'x\n', False)})
        mp, m = self.manifest(s, h)
        tp, sp = self.ticket(m, key=self.other_key)
        self.assertEqual(self.refused(mp, a, tp, sp, cp), 'INSTALL_REFUSED code=TICKET_BAD_SIGNATURE')
        tp, sp = self.ticket(m, ns='file')
        self.assertEqual(self.refused(mp, a, tp, sp, cp), 'INSTALL_REFUSED code=TICKET_BAD_SIGNATURE')
        tp, sp = self.ticket(m)
        with open(tp, 'r+b') as f:
            raw = f.read().replace(b'"v": 1', b'"v": 1 ')
            f.seek(0)
            f.write(raw)
        self.assertEqual(self.refused(mp, a, tp, sp, cp), 'INSTALL_REFUSED code=TICKET_BAD_SIGNATURE')
        tp, _ = self.ticket(m)
        empty = self.name('empty') + '.sig'
        open(empty, 'w').close()
        self.assertEqual(self.refused(mp, a, tp, empty, cp), 'INSTALL_REFUSED code=TICKET_BAD_SIGNATURE')

    def test_ticket_fields_and_time(self):
        h, a, s, cp = self.commit({'bot/x': (b'x\n', False)})
        mp, m = self.manifest(s, h)
        for k, v in (('head_sha', 'd' * 40), ('artifact_sha256', '0' * 64), ('manifest_sha256', '1' * 64),
                     ('repo_id', 7), ('tenant_id', str(uuid.uuid4())), ('work_item_id', str(uuid.uuid4()))):
            self.assertEqual(self.refused(mp, a, *self.ticket(m, **{k: v}), cp), 'INSTALL_REFUSED code=TICKET_MISMATCH', k)
        now = int(time.time())
        self.assertEqual(self.refused(mp, a, *self.ticket(m, issued=now - 1000, ttl=900), cp), 'INSTALL_REFUSED code=TICKET_EXPIRED')
        self.assertEqual(self.refused(mp, a, *self.ticket(m, ttl=7200), cp), 'INSTALL_REFUSED code=TICKET_BAD_FORMAT')
        self.assertEqual(self.refused(mp, a, *self.ticket(m, issued=now + 3000), cp), 'INSTALL_REFUSED code=TICKET_BAD_FORMAT')
        self.assertEqual(self.refused(mp, a, *self.ticket(m, tid='not-a-uuid'), cp), 'INSTALL_REFUSED code=TICKET_BAD_FORMAT')

    def signed(self, a, s, head, cp):
        mp, m = self.manifest(s, head)
        return (mp, a, *self.ticket(m), cp)

    def test_artifact_bound_to_signed_head_m_s6_r11_01(self):
        head, a, s, cp = self.commit({'bot/__main__.py': (b'print(1)\n', False), 'bot/run.sh': (b'#!/bin/sh\n', True)})
        # тот же путь, другой код; лишний файл; другой бит исполнения; пустая папка — подпись и repo/head верные
        for members in ([self.reg('bot/__main__.py', b'import os\nos.system("id")\n'), self.reg('bot/run.sh', b'#!/bin/sh\n', 0o755)],
                        [self.reg('bot/__main__.py', b'print(1)\n'), self.reg('bot/run.sh', b'#!/bin/sh\n', 0o755),
                         self.reg('bot/extra.py', b'x\n')],
                        [self.reg('bot/__main__.py', b'print(1)\n', 0o755), self.reg('bot/run.sh', b'#!/bin/sh\n', 0o755)],
                        [self.reg('bot/__main__.py', b'print(1)\n'), self.reg('bot/run.sh', b'#!/bin/sh\n', 0o755),
                         self.dir('bot/empty')]):
            fa, fs = self.tar_of(members)
            self.assertEqual(self.refused(*self.signed(fa, fs, head, cp)), 'INSTALL_REFUSED code=ARTIFACT_NOT_FROM_HEAD')
        # объект другого коммита и пустой объект — не тот head
        _, _, _, other_cp = self.commit({'bot/__main__.py': (b'print(2)\n', False)})
        self.assertEqual(self.refused(*self.signed(a, s, head, other_cp)), 'INSTALL_REFUSED code=COMMIT_NOT_HEAD')
        empty = self.name('c') + '.obj'
        open(empty, 'w').close()
        self.assertEqual(self.refused(*self.signed(a, s, head, empty)), 'INSTALL_REFUSED code=COMMIT_NOT_HEAD')
        self.assertFalse(os.path.lexists(os.path.join(self.root, 'current')))
        # тот же архив с тем же объектом — ставится
        r = self.run_install(*self.signed(a, s, head, cp))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f'INSTALL_OK state=installed head={head}', r.stdout)

    def test_commit_tree_passes_but_unsafe_name_still_refused(self):
        head, a, s, cp = self.commit({'.artifact_sha256': (b'0\n', False), 'bot/x': (b'x\n', False)})
        self.assertEqual(self.refused(*self.signed(a, s, head, cp)), 'INSTALL_REFUSED code=BAD_ARTIFACT_CONTENT')

    def hostile(self, members, code='BAD_ARTIFACT_CONTENT'):
        head, _, _, cp = self.commit({'bot/ok.py': (b'x', False)})
        a, s = self.tar_of(members)
        self.assertEqual(self.refused(*self.signed(a, s, head, cp)), f'INSTALL_REFUSED code={code}')
        self.assertFalse(os.path.lexists(os.path.join(self.root, 'releases', head)))

    def reg(self, name, data=b'x', mode=0o644, uid=0):
        ti = tarfile.TarInfo(name)
        ti.size, ti.mode, ti.uid, ti.gid = len(data), mode, uid, 0
        return ti, data

    def dir(self, name, mode=0o755):
        ti = tarfile.TarInfo(name)
        ti.type, ti.mode = tarfile.DIRTYPE, mode
        return ti, None

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
        # имена, допустимые в git, но не в выпуске: дерево не совпадает с head (а будь совпадение — отказ распаковки)
        self.hostile([self.reg('.artifact_sha256')], 'ARTIFACT_NOT_FROM_HEAD')
        self.hostile([self.reg('bot/a\nb')], 'ARTIFACT_NOT_FROM_HEAD')
        self.assertFalse(os.path.lexists(os.path.join(self.root, 'current')))

    def test_root_owned_tar_with_same_tree_is_installed_with_safe_modes(self):
        head, _, _, cp = self.commit({'bot/__main__.py': (b'print(1)\n', False), 'bot/run': (b'#!/bin/sh\n', True)})
        a, s = self.tar_of([self.dir('bot', 0o777), self.reg('bot/__main__.py', b'print(1)\n', mode=0o666, uid=0),
                            self.reg('bot/run', b'#!/bin/sh\n', mode=0o777, uid=0)])
        r = self.run_install(*self.signed(a, s, head, cp))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rel = os.path.join(self.root, 'releases', head)
        me = os.geteuid()
        for p, mode in ((os.path.join(rel, 'bot'), 0o755), (os.path.join(rel, 'bot', '__main__.py'), 0o644),
                        (os.path.join(rel, 'bot', 'run'), 0o755), (os.path.join(rel, '.artifact_sha256'), 0o644)):
            st = os.lstat(p)
            self.assertEqual(st.st_mode & 0o7777, mode, p)
            self.assertEqual(st.st_uid, me, p)


    # L-S6-R12-01 (v0.5): каждый объект пересчитывает git с детектором коллизий SHA1DC; без него или при его отказе — не ставится
    def fake_git(self, version_line, hash_body):
        p = self.name('git')
        with open(p, 'w') as f:
            f.write('#!/bin/sh\nif [ "$1" = version ]; then echo "git version 2.99"; echo "%s"; exit 0; fi\n%s\n'
                    % (version_line, hash_body))
        os.chmod(p, 0o755)
        return p

    def test_real_git_reports_sha1dc_or_nothing(self):
        out = subprocess.run(['/usr/bin/git', 'version', '--build-options'], capture_output=True, text=True,
                             check=True).stdout.lower().splitlines()
        lines = [x for x in out if x.startswith(('sha1:', 'sha-1:'))]
        self.assertTrue(all(x.split(':', 1)[1].strip() == 'sha1_dc' for x in lines), lines)

    def test_git_without_sha1dc_refused_l_s6_r12_01(self):
        self.git_bin = self.fake_git('SHA-1: OpenSSL', 'exec /usr/bin/git "$@"')
        self.assertEqual(self.refused(*self.release()), 'INSTALL_REFUSED code=GIT_NO_SHA1DC')
        self.git_bin = os.path.join(self.d, 'no-such-git')
        self.assertEqual(self.refused(*self.release()), 'INSTALL_REFUSED code=GIT_NO_SHA1DC')
        self.assertFalse(os.path.lexists(os.path.join(self.root, 'current')))

    def test_git_collision_or_lie_refused_l_s6_r12_01(self):
        # git с SHA1DC на половине пары коллизии печатает ошибку и выходит с кодом 128 — так его и имитируем
        self.git_bin = self.fake_git('SHA-1: SHA1_DC',
                                     'echo "fatal: SHA-1 appears to be part of a collision attack" >&2; exit 128')
        self.assertEqual(self.refused(*self.release()), 'INSTALL_REFUSED code=SHA1_GUARD_FAILED')
        self.git_bin = self.fake_git('SHA-1: SHA1_DC', 'echo 0000000000000000000000000000000000000000')
        self.assertEqual(self.refused(*self.release()), 'INSTALL_REFUSED code=SHA1_GUARD_FAILED')
        self.assertFalse(os.path.lexists(os.path.join(self.root, 'current')))
        # git без строки SHA-1 в --build-options (старые версии) допускается, но хеши всё равно считает он
        self.git_bin = self.fake_git('built from commit: x', 'exec /usr/bin/git "$@"')
        r = self.run_install(*self.release())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('INSTALL_OK state=installed', r.stdout)

    def test_git_batched_for_large_release_m_r13_01(self):
        # M-R13-01: git считает объекты пачками — коммит, файлы, деревья; не по запуску на объект
        log = os.path.join(self.d, 'git_calls.log')
        self.git_bin = self.fake_git('SHA-1: SHA1_DC', 'echo "$*" >> %s; exec /usr/bin/git "$@"' % log)
        files = {f'bot/d{i // 3}/s{i % 3}/f{i}.py': (f'print({i})\n'.encode(), i % 7 == 0) for i in range(1200)}
        head, a, s, cp = self.commit(files)
        started = time.monotonic()
        r = self.run_install(*self.signed(a, s, head, cp))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f'INSTALL_OK state=installed head={head}', r.stdout)
        self.assertLess(time.monotonic() - started, 120)
        with open(log) as f:
            calls = [x for x in f.read().splitlines() if x.startswith('hash-object')]
        self.assertLessEqual(len(calls), 3, calls)
        self.assertEqual(sorted(x.split()[3] for x in calls), ['blob', 'commit', 'tree'])


if __name__ == '__main__':
    unittest.main()
