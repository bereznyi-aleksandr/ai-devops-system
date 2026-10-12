# ДОКУМЕНТ: zavod/ops/sqlite_backup.py
# ВЕРСИЯ: v0.2  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 08:38 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-12 10:32 +03:00 (v0.2: аудит ChatGPT
#   S6-prep L-S6-02 — восстановление обязательно получает ожидаемый SHA-256 манифеста из доверенного места
#   (журнал копий, evidence Kernel); не совпал — MANIFEST_UNTRUSTED до любой записи: согласованная подмена
#   копии и манифеста больше не проходит)
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: этап 6, критерий E6-3 — копия базы SQLite продукта и восстановление на чистом месте со сверкой
#   отпечатков. Копия снимается онлайн-API SQLite (Connection.backup), а не копированием файла на ходу.
#   Рядом с копией пишется манифест: SHA-256 файла копии и логический отпечаток данных (схема и строки всех
#   таблиц в устойчивом порядке, значения с типом). Восстановление: папка назначения пуста или отсутствует →
#   SHA-256 копии совпал с манифестом (до любой записи) → файл пишется под временным именем → PRAGMA
#   integrity_check = ok → отпечаток совпал → только тогда переименование в итоговое имя. Отказ — RestoreRefused
#   с кодом; недоделанный файл не удаляется, а остаётся с суффиксом .refused (правило проекта: ничего не удалять).
# ОГРАНИЧЕНИЯ: только stdlib Python 3. Секретов не читает и не пишет; содержимое строк в журнал не попадает —
#   только суммы и число строк. Шифрование и вывоз копии с сервера — вне v0.1.
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

VERSION = 'v0.1'


class RestoreRefused(Exception):
    def __init__(self, code, message):
        super().__init__(f'{code}: {message}')
        self.code = code


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 16), b''):
            h.update(chunk)
    return h.hexdigest()


def _cell(v):
    if v is None:
        return ['n']
    if isinstance(v, int):
        return ['i', str(v)]
    if isinstance(v, float):
        return ['f', repr(v)]
    if isinstance(v, bytes):
        return ['b', v.hex()]
    return ['t', v]


def fingerprint(path):
    """Логический отпечаток: не зависит от раскладки страниц файла, меняется от любой правки данных или схемы."""
    con = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    try:
        h = hashlib.sha256()
        counts = {}
        tables = con.execute("SELECT name, sql FROM sqlite_master WHERE type='table' "
                             "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        for name, sql in tables:
            h.update(json.dumps(['table', name, sql], ensure_ascii=False).encode('utf-8') + b'\n')
            q = '"' + name.replace('"', '""') + '"'
            ncols = len(con.execute(f'SELECT * FROM {q} LIMIT 0').description)
            order = ', '.join(str(i) for i in range(1, ncols + 1))
            n = 0
            for row in con.execute(f'SELECT * FROM {q} ORDER BY {order}'):
                h.update(json.dumps([_cell(v) for v in row], ensure_ascii=False).encode('utf-8') + b'\n')
                n += 1
            counts[name] = n
        for kind, name, sql in con.execute("SELECT type, name, sql FROM sqlite_master WHERE type IN ('index','trigger','view') "
                                           "AND sql IS NOT NULL ORDER BY type, name"):
            h.update(json.dumps([kind, name, sql], ensure_ascii=False).encode('utf-8') + b'\n')
        return h.hexdigest(), counts
    finally:
        con.close()


def backup(db_path, out_dir, now=None):
    if not os.path.isfile(db_path):
        raise FileNotFoundError(db_path)
    os.makedirs(out_dir, exist_ok=True)
    stamp = (now or datetime.now(timezone.utc)).strftime('%Y%m%dT%H%M%SZ')
    base = os.path.splitext(os.path.basename(db_path))[0]
    out = os.path.join(out_dir, f'{base}.{stamp}.sqlite')
    if os.path.exists(out):
        raise FileExistsError(out)
    src = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    dst = sqlite3.connect(out)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    fp, counts = fingerprint(out)
    manifest = {
        'tool': f'zavod/ops/sqlite_backup.py {VERSION}',
        'created_at': stamp,
        'source_name': os.path.basename(db_path),
        'backup_file': os.path.basename(out),
        'backup_sha256': file_sha256(out),
        'fingerprint': fp,
        'rows': counts,
    }
    mpath = out + '.manifest.json'
    with open(mpath, 'x', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write('\n')
    return manifest, out, mpath


def restore(backup_path, manifest_path, target_dir, expected_manifest_sha256, target_name='restored.sqlite'):
    if not (isinstance(expected_manifest_sha256, str) and len(expected_manifest_sha256) == 64
            and file_sha256(manifest_path) == expected_manifest_sha256):
        raise RestoreRefused('MANIFEST_UNTRUSTED', 'manifest differs from the trusted manifest sha256')
    with open(manifest_path, encoding='utf-8') as f:
        m = json.load(f)
    if os.path.basename(backup_path) != m.get('backup_file'):
        raise RestoreRefused('MANIFEST_OTHER_FILE', 'manifest names another backup file')
    if os.path.exists(target_dir) and os.listdir(target_dir):
        raise RestoreRefused('TARGET_NOT_CLEAN', 'target directory is not empty')
    got = file_sha256(backup_path)
    if got != m.get('backup_sha256'):
        raise RestoreRefused('SHA_MISMATCH', 'backup file bytes differ from manifest')
    os.makedirs(target_dir, exist_ok=True)
    tmp = os.path.join(target_dir, target_name + '.restoring')
    src = sqlite3.connect(f'file:{backup_path}?mode=ro', uri=True)
    dst = sqlite3.connect(tmp)
    try:
        src.backup(dst)
        ok = dst.execute('PRAGMA integrity_check').fetchone()[0]
    finally:
        dst.close()
        src.close()
    if ok != 'ok':
        os.replace(tmp, tmp[:-len('.restoring')] + '.refused')
        raise RestoreRefused('INTEGRITY', 'integrity_check failed')
    fp, counts = fingerprint(tmp)
    if fp != m.get('fingerprint'):
        os.replace(tmp, tmp[:-len('.restoring')] + '.refused')
        raise RestoreRefused('FINGERPRINT_MISMATCH', 'restored data differ from manifest')
    final = os.path.join(target_dir, target_name)
    os.replace(tmp, final)
    return {'restored': final, 'backup_sha256': got, 'fingerprint': fp, 'rows': counts, 'integrity': ok}


def main(argv):
    try:
        if len(argv) == 3 and argv[0] == 'backup':
            m, out, mpath = backup(argv[1], argv[2])
            print(json.dumps({'result': 'BACKUP_OK', **m, 'manifest_sha256': file_sha256(mpath)}, ensure_ascii=False))
            return 0
        if len(argv) == 5 and argv[0] == 'restore':
            r = restore(argv[1], argv[2], argv[4], argv[3])
            print(json.dumps({'result': 'RESTORE_OK', **r}, ensure_ascii=False))
            return 0
    except RestoreRefused as e:
        print(json.dumps({'result': 'RESTORE_REFUSED', 'code': e.code}))
        return 3
    print('usage: sqlite_backup.py backup DB OUT_DIR | restore BACKUP MANIFEST MANIFEST_SHA256 TARGET_DIR', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
