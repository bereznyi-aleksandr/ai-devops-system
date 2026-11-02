# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow9.py — проба карты 3.3.10.2 (аудит M3310-R8-03): пример
#   аудитора дословно и соседние пути: SQL в нижнем регистре, места выполнения запроса с не постоянным текстом.
# ДАТА: 2026-11-02 04:16 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
import subprocess
def run(cursor,value): cursor.execute('select * from t where id=' + value)
def many(cursor, rows, text):
    cursor.executemany(text, rows)
def pipe(sql):
    return subprocess.run(['psql', '-X', '-f', '-'], input=sql, text=True)
def caller(value):
    return pipe('SELECT 1 WHERE x = ' + value)
def code(cursor, s):
    eval(s)
    getattr(cursor, 'exe' + 'cute')('SELECT 1')
