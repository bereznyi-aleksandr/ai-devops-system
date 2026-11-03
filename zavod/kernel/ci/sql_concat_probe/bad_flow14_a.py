# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow14_a.py — проба 3.3.10.2 (аудит M3310-R13-01, -02): примеры
#   аудитора — функция, которую другой файл (bad_flow14_b.py) вызывает с любым текстом; .fetch и .copy.
# ДАТА: 2026-11-02 09:06 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
def send(cur, sql): return cur.execute(sql)
def smoke(cur): return send(cur, 'SELECT 1')
async def run(conn, supplied_sql): return await conn.fetch(supplied_sql)
def run2(cur, supplied_sql): return cur.copy(supplied_sql)
async def ok(conn): return await conn.fetch('SELECT 1')
