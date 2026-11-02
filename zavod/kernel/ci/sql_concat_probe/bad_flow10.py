# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow10.py — проба карты 3.3.10.2 (аудит M3310-R9-02, -03, -04):
#   примеры аудитора дословно и соседние пути: метод запроса под другим именем, цикл доказательства, запуск psql.
# ДАТА: 2026-11-02 04:52 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
import os
import subprocess
def run(cur, incoming):
    send = cur.execute
    return send(incoming)
def rec(cur, incoming):
    cur.execute(incoming)
    return rec(cur, incoming)
def shell(incoming):
    return subprocess.run('psql -f -', input=incoming, text=True, shell=True)
def joined(incoming):
    return subprocess.run(['ps'+'ql','-f','-'],input=incoming,text=True)
def other(incoming, cmd):
    s = subprocess
    os.system(cmd)
    argv = ['psql', '-X', '-f', '-']
    argv.append('-c')
    subprocess.run(argv, input='SELECT 1', text=True)
    subprocess.run(['sudo', 'sh', '-c', cmd])
