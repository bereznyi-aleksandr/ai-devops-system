# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow14_b.py — пара к bad_flow14_a.py (аудит M3310-R13-01): внешний
#   вызов с текстом из параметра; находка — в bad_flow14_a.py:4 (параметр функции верхнего уровня не постоянный).
# ДАТА: 2026-11-02 09:06 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
from bad_flow14_a import send
def entry(cur, supplied_sql): return send(cur, supplied_sql)
