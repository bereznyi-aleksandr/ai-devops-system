# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow17.py — проба 3.3.10.2 (аудит M3310-R15B-03): метод по
#   заглавному имени у объекта, который не модуль из закрытого списка.
# ДАТА: 2026-11-02 15:09 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
def run(adapter, supplied_sql):
    return getattr(adapter, 'EXECUTE')(supplied_sql)
