# ДОКУМЕНТ: zavod/ops/tests/test_key_origin.py
# ВЕРСИЯ: v0.2  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 15:26 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-12 16:01 +03:00 (v0.2: аудит R10 L-S6-R10-01 — на
#   Windows проверки идут именно программой C:\Windows\System32\OpenSSH\ssh-keygen.exe, если она есть, а не первой
#   из PATH; на Linux — ssh-keygen из PATH.)
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: аудит ChatGPT S6-prep R9, M-S6-R9-01, критерии R10-1 и R10-2 — источник отпечатка ключа не файл.
#   OD-5 v2.2: оператор переписывает отпечаток из вывода ssh-keygen В МОМЕНТ СОЗДАНИЯ ключа (строка после
#   «The key fingerprint is:»): его печатает тот же процесс, что создал ключ в памяти, до записи файлов. Здесь
#   показано: (1) этот отпечаток совпадает с ключом, который реально записан; (2) если затем агент заменит ОБА
#   файла (закрытый и .pub) своей парой, прежний способ (`ssh-keygen -lf` по закрытому файлу) отдаёт отпечаток
#   агента, а отпечаток с бумаги — нет: render_user_data отказывает (ключ подписи), во 2-й строке user-data
#   стоят отпечатки агента, которых нет на бумаге оператора, — сверка на телефоне (OD-5 шаг 7) останавливает
#   создание сервера. То же для ключа zadmin.
# ОГРАНИЧЕНИЯ: нужен ssh-keygen (иначе пропуск); ключи тестовые без пароля; временные файлы —
#   tempfile.TemporaryDirectory (четыре условия P4.718 как в test_sqlite_backup.py v0.1).
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'server'))
import render_user_data as ru  # noqa: E402

TGT = (1412203481, 'bereznyi-aleksandr/zavod-p1-bot', '48d39de1-2c46-4deb-8557-fec866f2e810')
GEN_FP = re.compile(r'The key fingerprint is:\s*(SHA256:[A-Za-z0-9+/]{43}) ')


S32 = r'C:\Windows\System32\OpenSSH\ssh-keygen.exe'


def keygen():
    return S32 if os.name == 'nt' and os.path.exists(S32) else shutil.which('ssh-keygen')


@unittest.skipUnless(keygen(), 'нужен ssh-keygen')
class KeyOriginTest(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.d = self._td.name

    def tearDown(self):
        self._td.cleanup()

    def gen(self, name):
        # как в OD-5 шаги 2, 3, 3а: без -q, отпечаток читается из вывода самого создания
        f = os.path.join(self.d, name)
        out = subprocess.run([keygen(), '-t', 'ed25519', '-N', '', '-C', name, '-f', f],
                             check=True, capture_output=True, text=True).stdout
        m = GEN_FP.search(out)
        self.assertIsNotNone(m, out)
        return f, m.group(1)

    def lf(self, path):
        return subprocess.run([keygen(), '-lf', path], check=True, capture_output=True, text=True).stdout.split()[1]

    def swap(self, victim, agent):
        # подмена пары: агент той же учётной записи пишет свои закрытый и открытый файлы на место оператора
        for ext in ('', '.pub'):
            shutil.copyfile(agent + ext, victim + ext)

    def test_generation_output_is_the_written_key(self):
        f, paper = self.gen('release')
        self.assertEqual(self.lf(f), paper)
        self.assertEqual(ru.fingerprint(ru.read_pub(f + '.pub')), paper)

    def test_paired_substitution_release_key_m_s6_r9_01(self):
        rel, paper = self.gen('release')
        adm, _ = self.gen('admin')
        dep, _ = self.gen('deploy')
        agent, agent_fp = self.gen('agent')
        self.swap(rel, agent)
        self.assertEqual(self.lf(rel), agent_fp, 'старый способ (-lf по файлу) отдал бы отпечаток агента')
        self.assertNotEqual(agent_fp, paper)
        A, D, S = (ru.read_pub(p + '.pub') for p in (adm, dep, rel))
        with self.assertRaises(SystemExit) as e:
            ru.render(A, D, S, *TGT, release_fp=paper)
        self.assertIn('does not match the operator fingerprint', str(e.exception))
        # агент собирает файл со своим отпечатком: во 2-й строке нет отпечатка с бумаги — на телефоне не совпадёт
        second = ru.render(A, D, S, *TGT, release_fp=agent_fp).split('\n')[1]
        self.assertIn('RELEASE_KEY_FINGERPRINT ' + agent_fp + ';', second)
        self.assertNotIn(paper, second)

    def test_paired_substitution_admin_key_m_s6_r9_01(self):
        rel, rel_paper = self.gen('release')
        adm, paper = self.gen('admin')
        dep, _ = self.gen('deploy')
        agent, agent_fp = self.gen('agent')
        self.swap(adm, agent)
        self.assertEqual(self.lf(adm), agent_fp)
        A, D, S = (ru.read_pub(p + '.pub') for p in (adm, dep, rel))
        second = ru.render(A, D, S, *TGT, release_fp=rel_paper).split('\n')[1]
        self.assertIn('ADMIN_KEY_FINGERPRINT ' + agent_fp + ' ', second)
        self.assertNotIn(paper, second)


if __name__ == '__main__':
    unittest.main()
