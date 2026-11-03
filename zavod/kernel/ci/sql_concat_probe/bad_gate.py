# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_gate.py — проба карты 3.3.10.2: так писать нельзя, сборка обязана упасть.
# ДАТА: 2026-11-01 22:56 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
def accept(lease, text):
    a = f"SELECT bem_control.gate_accept('{lease}')"
    b = "INSERT INTO bem_control.gate_command (args) VALUES ('" + text + "')"
    c = "DELETE FROM bem_control.gate_command WHERE nonce = '%s'" % text
    d = "UPDATE bem_control.chat_lease SET status = '{}'".format(text)
    return a, b, c, d
