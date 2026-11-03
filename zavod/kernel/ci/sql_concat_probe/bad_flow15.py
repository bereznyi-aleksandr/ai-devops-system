# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow15.py — проба 3.3.10.2 (аудит M3310-R14-01, -02): примеры
#   аудитора — global и nonlocal меняют постоянный текст; сторонний модуль с функцией-запросом (execute_values, read_sql).
# ДАТА: 2026-11-02 10:25 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
sql = 'SELECT 1'
def set_sql(incoming):
    global sql
    sql = incoming
def send(cur):
    return cur.execute(sql)
def outer(cur, incoming):
    q = 'SELECT 2'
    def change():
        nonlocal q
        q = incoming
    change()
    def go():
        return cur.execute(q)
    return go()
from psycopg2.extras import execute_values
import pandas
def run(cur, supplied_sql, rows, con):
    execute_values(cur, supplied_sql, rows)
    return pandas.read_sql(supplied_sql, con)
