# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow11.py — проба карты 3.3.10.2 (аудит M3310-R10-05, -06, -07): примеры
#   аудитора; строки «import …; def …» разнесены по строкам (в Python def после ; не разбирается), сам код тот же.
# ДАТА: 2026-11-02 07:05 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
import subprocess
import builtins
import importlib
prog='git'
def run(incoming): subprocess.run(['psql','-c'+incoming])
def run2(incoming): subprocess.run(['psql','--command='+incoming])
def run3(prog,sql): subprocess.run([prog,'-c',sql])
def run4(code): return builtins.eval(code)
def run5(code):
    cp=importlib.import_module('subprocess'); cp.run(['sh','-c',code])
def run6(code):
    return getattr(builtins, 'exec')(code)
def run7(code):
    return globals()['eval'](code)
