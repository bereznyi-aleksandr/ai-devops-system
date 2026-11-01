# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow2.py — проба карты 3.3.10.2 (аудит M3310-R2-01): текст запроса
#   из функции этого файла и из массива; так писать нельзя, сборка обязана упасть.
# ДАТА: 2026-11-02 01:15 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)


def head():
    return 'SELECT * FROM bem_control.gate_command WHERE lease_id = '


def from_function(cur, lease):
    cur.execute(head() + lease)


def from_array(cur, table):
    parts = ['SELECT * FROM', table]
    cur.execute(' '.join(parts))
