# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow13.py — проба карты 3.3.10.2 (аудит M3310-R12-01..03): примеры
#   аудитора — getattr и eval/exec под другим именем, правка sys.path для импорта из архива (архив — extra13.zip).
# ДАТА: 2026-11-02 08:40 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
import sys
def run(cur, sql):
    pick = getattr
    return pick(cur, 'execute')(sql)
def run2(code):
    fn = eval
    return fn(code)
def run3(code):
    fn = exec
    return fn(code)
sys.path.insert(0, 'zavod/kernel/src/extras.zip')
from hidden import run as hrun
def call(cur, sql): return hrun(cur, sql)
