# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow12.py — проба карты 3.3.10.2 (аудит M3310-R11-01, -02): примеры
#   аудитора; «import …; def …» разнесены по строкам (в Python def после ; не разбирается), сам код тот же.
# ДАТА: 2026-11-02 07:26 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
import os
import sys
def run(cur,sql): return cur.__getattribute__('execute')(sql)
def run2(cmd): return os.__dict__['system'](cmd)
def run3(code): return run3.__globals__['__builtins__'].__dict__['eval'](code)
def run4(sql): return sys.modules['subprocess'].run(['psql','-c',sql])
def run5(cur, sql): return getattr(cur, 'execute')(sql)
def run6(o, cmd): return o.system(cmd)
def run7(): return sys._getframe(1).f_globals
