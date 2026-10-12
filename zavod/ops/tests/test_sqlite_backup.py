# ДОКУМЕНТ: zavod/ops/tests/test_sqlite_backup.py
# ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 08:38 +03:00
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: модульные проверки zavod/ops/sqlite_backup.py (E6-3): точная копия восстанавливается с тем же
#   отпечатком; копия снимается при открытой пишущей базе в режиме WAL; порча байта копии, чужой манифест,
#   непустая папка назначения, подмена отпечатка в манифесте — отказ; отпечаток не зависит от раскладки файла
#   (VACUUM), но меняется от правки одной строки.
# ОГРАНИЧЕНИЯ: временные папки — tempfile.TemporaryDirectory. Проверка четырёх условий P4.718 записана здесь:
#   (1) создаются кодом в tmpdir ОС, вне CANONICAL_ROOT и RUNTIME_ROOT; (2) создаются и убираются внутри одного
#   теста одного процесса; (3) итог фиксирует вывод unittest, не содержимое папок; (4) в них только синтетические
#   данные теста, без пользовательских данных и чужих доказательств.
import json
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import sqlite_backup as sb  # noqa: E402


def make_db(path, rows=20):
    con = sqlite3.connect(path)
    con.execute('CREATE TABLE applications (id INTEGER PRIMARY KEY, chat_id INTEGER, name TEXT, phone TEXT, '
                'comment TEXT, score REAL, raw BLOB)')
    con.executemany('INSERT INTO applications (chat_id, name, phone, comment, score, raw) VALUES (?,?,?,?,?,?)',
                    [(1000 + i, f'Имя {i}', f'+38044000{i:04d}', None if i % 3 else 'тест', i / 7, bytes([i % 256]) * 3)
                     for i in range(rows)])
    con.execute('CREATE INDEX ix_chat ON applications(chat_id)')
    con.commit()
    con.close()


class SqliteBackupTest(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.d = self._td.name
        self.db = os.path.join(self.d, 'p1.sqlite')
        make_db(self.db)

    def tearDown(self):
        self._td.cleanup()

    def bk(self):
        return sb.backup(self.db, os.path.join(self.d, 'bk'))

    def test_exact_backup_restores_with_same_fingerprint(self):
        m, out, mp = self.bk()
        fp0, counts0 = sb.fingerprint(self.db)
        self.assertEqual(m['fingerprint'], fp0)
        self.assertEqual(m['rows'], {'applications': 20})
        r = sb.restore(out, mp, os.path.join(self.d, 'clean'))
        self.assertEqual(r['fingerprint'], fp0)
        self.assertEqual(r['integrity'], 'ok')
        self.assertEqual(sorted(os.listdir(os.path.join(self.d, 'clean'))), ['restored.sqlite'])

    def test_backup_while_writer_open_in_wal(self):
        w = sqlite3.connect(self.db)
        w.execute('PRAGMA journal_mode=WAL')
        w.execute("INSERT INTO applications (chat_id, name) VALUES (1, 'в журнале WAL')")
        w.commit()
        try:
            m, out, mp = self.bk()
            self.assertEqual(m['rows'], {'applications': 21})
            r = sb.restore(out, mp, os.path.join(self.d, 'clean'))
            self.assertEqual(r['fingerprint'], sb.fingerprint(self.db)[0])
        finally:
            w.close()

    def test_tampered_byte_refused_before_any_write(self):
        m, out, mp = self.bk()
        with open(out, 'r+b') as f:
            f.seek(os.path.getsize(out) - 10)
            b = f.read(1)
            f.seek(-1, 1)
            f.write(bytes([b[0] ^ 1]))
        target = os.path.join(self.d, 'clean')
        with self.assertRaises(sb.RestoreRefused) as c:
            sb.restore(out, mp, target)
        self.assertEqual(c.exception.code, 'SHA_MISMATCH')
        self.assertFalse(os.path.exists(target))

    def test_target_not_clean_refused(self):
        m, out, mp = self.bk()
        target = os.path.join(self.d, 'busy')
        os.makedirs(target)
        open(os.path.join(target, 'live.sqlite'), 'wb').close()
        with self.assertRaises(sb.RestoreRefused) as c:
            sb.restore(out, mp, target)
        self.assertEqual(c.exception.code, 'TARGET_NOT_CLEAN')

    def test_manifest_of_other_file_refused(self):
        m, out, mp = self.bk()
        with open(mp, encoding='utf-8') as f:
            j = json.load(f)
        j['backup_file'] = 'other.sqlite'
        with open(mp, 'w', encoding='utf-8') as f:
            json.dump(j, f)
        with self.assertRaises(sb.RestoreRefused) as c:
            sb.restore(out, mp, os.path.join(self.d, 'clean'))
        self.assertEqual(c.exception.code, 'MANIFEST_OTHER_FILE')

    def test_fingerprint_mismatch_refused_and_kept_as_refused(self):
        m, out, mp = self.bk()
        with open(mp, encoding='utf-8') as f:
            j = json.load(f)
        j['fingerprint'] = '0' * 64
        with open(mp, 'w', encoding='utf-8') as f:
            json.dump(j, f)
        target = os.path.join(self.d, 'clean')
        with self.assertRaises(sb.RestoreRefused) as c:
            sb.restore(out, mp, target)
        self.assertEqual(c.exception.code, 'FINGERPRINT_MISMATCH')
        self.assertEqual(os.listdir(target), ['restored.sqlite.refused'])

    def test_fingerprint_ignores_layout_but_sees_one_row(self):
        fp0 = sb.fingerprint(self.db)[0]
        sz0 = sb.file_sha256(self.db)
        con = sqlite3.connect(self.db)
        con.execute('INSERT INTO applications (chat_id) VALUES (5)')
        con.commit()
        con.execute('DELETE FROM applications WHERE chat_id = 5')
        con.commit()
        con.execute('VACUUM')
        con.close()
        self.assertEqual(sb.fingerprint(self.db)[0], fp0)
        self.assertNotEqual(sb.file_sha256(self.db), sz0)
        con = sqlite3.connect(self.db)
        con.execute("UPDATE applications SET phone = '+380440009999' WHERE id = 3")
        con.commit()
        con.close()
        self.assertNotEqual(sb.fingerprint(self.db)[0], fp0)

    def test_backup_never_overwrites(self):
        from datetime import datetime, timezone
        now = datetime(2026, 10, 12, tzinfo=timezone.utc)
        sb.backup(self.db, os.path.join(self.d, 'bk'), now=now)
        with self.assertRaises(FileExistsError):
            sb.backup(self.db, os.path.join(self.d, 'bk'), now=now)


if __name__ == '__main__':
    unittest.main()
