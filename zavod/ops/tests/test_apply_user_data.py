# ДОКУМЕНТ: zavod/ops/tests/test_apply_user_data.py
# ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 15:26 +03:00
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: аудит ChatGPT S6-prep R9, L-S6-R9-01 — apply_user_data.py не пропускает молча поля безопасности.
#   Канонический user-data проходит; лишнее поле верхнего уровня, пользователя или файла — отказ; disable_root не
#   true или ssh_pwauth не false — отказ; действующие настройки sshd (`sshd -T`), где root или пароль разрешены, —
#   отказ с перечнем расхождений. Боевая проверка `sshd -T` от root идёт в CI через стартер (zavod-kernel.yml).
# ОГРАНИЧЕНИЯ: на Windows нет модуля pwd — для импорта подставляется пустая заглушка (функции, где он нужен, здесь
#   не вызываются).
import base64
import json
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'server'))
if 'pwd' not in sys.modules:
    try:
        import pwd  # noqa: F401
    except ImportError:
        sys.modules['pwd'] = types.ModuleType('pwd')
import apply_user_data as au  # noqa: E402
import render_user_data as ru  # noqa: E402


def ed(fill, comment):
    raw = len(b'ssh-ed25519').to_bytes(4, 'big') + b'ssh-ed25519' + (32).to_bytes(4, 'big') + bytes([fill]) * 32
    return 'ssh-ed25519 ' + base64.b64encode(raw).decode('ascii') + ' ' + comment


A, D, S = ed(1, 'admin@test'), ed(2, 'deploy@test'), ed(3, 'release@test')
TGT = (1412203481, 'bereznyi-aleksandr/zavod-p1-bot', '48d39de1-2c46-4deb-8557-fec866f2e810')
GOOD = ru.render(A, D, S, *TGT, release_fp=ru.fingerprint(S))
SSHD_OK = ('port 22\npermitrootlogin no\npubkeyauthentication yes\npasswordauthentication no\n'
           'kbdinteractiveauthentication no\nauthenticationmethods publickey\nallowusers zadmin\nallowusers zavod\n')


def cfg():
    return json.loads(GOOD.split('\n', 2)[2])


class ApplyValidateTest(unittest.TestCase):
    def test_canonical_user_data_accepted(self):
        c = cfg()
        self.assertIs(au.validate(c), c)
        self.assertIs(c['disable_root'], True)
        self.assertIs(c['ssh_pwauth'], False)

    def test_unknown_fields_refused(self):
        for mutate, why in [
            (lambda c: c.update(bootcmd=[['sh', '-c', 'id']]), 'top-level field bootcmd'),
            (lambda c: c.update(chpasswd={'expire': False}), 'top-level field chpasswd'),
            (lambda c: c['users'][0].update(passwd='$6$x'), 'user field passwd'),
            (lambda c: c['write_files'][0].update(append=True), 'write_files field append'),
        ]:
            c = cfg()
            mutate(c)
            with self.assertRaises(SystemExit) as e:
                au.validate(c)
            self.assertIn(why, str(e.exception))

    def test_security_fields_must_be_canonical_l_s6_r9_01(self):
        for k, v in [('disable_root', False), ('disable_root', None), ('ssh_pwauth', True), ('ssh_pwauth', None)]:
            c = cfg()
            if v is None:
                del c[k]
            else:
                c[k] = v
            with self.assertRaises(SystemExit) as e:
                au.validate(c)
            self.assertIn('disable_root must be true and ssh_pwauth false', str(e.exception))

    def test_effective_sshd_settings(self):
        self.assertEqual(au.sshd_mismatch(SSHD_OK), [])
        bad = SSHD_OK.replace('permitrootlogin no', 'permitrootlogin prohibit-password')
        self.assertEqual(au.sshd_mismatch(bad), ["permitrootlogin='prohibit-password' (need 'no')"])
        bad = SSHD_OK.replace('passwordauthentication no', 'passwordauthentication yes')
        self.assertEqual(au.sshd_mismatch(bad), ["passwordauthentication='yes' (need 'no')"])
        bad = SSHD_OK.replace('authenticationmethods publickey\n', '')
        self.assertEqual(au.sshd_mismatch(bad), ["authenticationmethods=None (need 'publickey')"])
        self.assertEqual(len(au.sshd_mismatch('')), 5)

    def test_sshd_drop_in_sets_what_is_checked(self):
        conf = dict(line.split(' ', 1) for line in ru.SSHD.strip().split('\n'))
        for k, v in au.SSHD_EFFECTIVE.items():
            name = next(n for n in conf if n.lower() == k)
            self.assertEqual(conf[name], v, k)


if __name__ == '__main__':
    unittest.main()
