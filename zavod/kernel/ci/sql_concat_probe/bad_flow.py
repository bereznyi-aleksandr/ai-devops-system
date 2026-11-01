# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow.py — проба карты 3.3.10.2 (аудит M3310-R1B-02): склейка через
#   переменные и куски; так писать нельзя, сборка обязана упасть.
# ДАТА: 2026-11-02 00:11 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)


def appended(cur, lease):
    query = 'SELECT * FROM bem_control.gate_command WHERE lease_id = '
    query += lease
    cur.execute(query)


def through_name(cur, lease):
    head = 'DELETE FROM bem_control.gate_command'
    tail = ' WHERE lease_id = '
    sql = head + tail
    sql = sql + lease
    cur.execute(sql)


def pieces(cur, table):
    cur.execute('SEL' + 'ECT * FROM ' + table)


def joined_list(cur, cols):
    parts = ['SELECT', cols, 'FROM bem_control.gate_command']
    cur.execute(' '.join(parts))
