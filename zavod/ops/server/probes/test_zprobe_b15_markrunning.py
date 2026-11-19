#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_b15_markrunning.py
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-19 14:25 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 14:25 +02:00
# ИСПОЛНИТЕЛЬ: Claude (терминал zavod, пускатель) — B15 (копия test_zprobe_b14_markrunning.py v0.2; файл B14 —
#   в задании b14-frozen на 43451be79)
# НАЗНАЧЕНИЕ: те же проверки отметки «работает» на бегунке B15. Отличие — бюджет: B15 П3 даёт прямому git push
#   DIRECT_PUSH_S + 2 с вместо 62 с (13 адресов, 8 имён: 951 с при DIRECT_PUSH_S = 180); M15 — запись старта S
#   (startrec) стоит в run() до аренды и до отметки «работает».
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zprobe_runner as N  # noqa: E402
import zprobe_rules as R  # noqa: E402

OK, BAD = [], []


def case(name, cond):
    (OK if cond else BAD).append(name)
    print(('PASS ' if cond else 'FAIL ') + name, flush=True)


def aborts(fn, *a):
    try:
        fn(*a)
    except N.Abort as e:
        return str(e)
    return None


# 1. Бюджет: формула и замер pb1trial3 (8,5 с на пробу tcp; 13 адресов → только tcp 221 с — больше 2 минут и
#    больше прежнего окна 300 с вместе с push и посредником).
case('M01 budget formula 13 targets, 8 names = 951 s (DIRECT_PUSH_S 180)',
     N.DIRECT_PUSH_S == 180 and N.collect_budget(13, 8) == 951)
case('M02 budget covers measured tcp 8.5 s/probe', N.collect_budget(13, 8) - 10 - 2 * 62 - (N.DIRECT_PUSH_S + 2) - 11 * 31 - 60 >= 13 * 2 * 8.5)
case('M03 budget of pb1trial3 > old window 300 s', N.collect_budget(13, len(R.GH_NAMES)) > 300)
case('M04 bad input refused', aborts(N.collect_budget, -1, 8) == 'budget_bad_input'
     and aborts(N.collect_budget, 3, -1) == 'budget_bad_input' and aborts(N.collect_budget, '3', 8) == 'budget_bad_input')
# 2. Проверка бюджета до аренды: предел MAX_TARGETS помещается; превышение — отказ с числами.
big = N.collect_budget(R.MAX_TARGETS, len(R.GH_NAMES))
case('M05 MAX_TARGETS budget fits with 300 s elapsed', aborts(N.budget_check, big, 300) is None)
case('M06 over budget refused with numbers',
     aborts(N.budget_check, N.RUN_TIMEOUT, 0) == f'budget_{N.RUN_TIMEOUT}_exceeds_{N.RUN_TIMEOUT - N.RUN_RESERVE}')
case('M07 elapsed counts against room', aborts(N.budget_check, 1000, N.RUN_TIMEOUT - N.RUN_RESERVE - 999) is not None)

# 3. Порядок шагов в run() по тексту программы.
src = open(os.path.join(HERE, 'zprobe_runner.py'), encoding='utf-8').read()
tree = ast.parse(src)
run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
steps, marks, loops60 = [], [], 0
for node in ast.walk(run):
    if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Subscript)
            and isinstance(node.value, ast.Constant) and ast.unparse(node.targets[0]) == "ev['step']"):
        steps.append((node.lineno, node.value.value))
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and 'lease_mark_running' in node.value:
        marks.append(node.lineno)
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'range'
            and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == 60):
        loops60 += 1
line = {name: ln for ln, name in steps}
case('M08 lease_mark_running called exactly once in runner', src.count('lease_mark_running(') == 1 and len(marks) == 1)
case('M09 mark_running after start step', bool(marks) and marks[0] > line.get('start', 10 ** 9))
case('M10 mark_running before collect step', bool(marks) and marks[0] < line.get('collect', -1))
case('M11 mark_running not in stop step', bool(marks) and not (line.get('stop', 10 ** 9) < marks[0]))
case('M12 collect window not fixed 60 polls; bounded by run deadline (v0.18)', loops60 == 0
     and "deadline = min(time.monotonic() + ev['collect_budget_s'], run_deadline())" in src)
case('M13 non-RUNNING answer aborts', "raise Abort('mark_running_' + ev['mark_running'])" in src)
case('M14 budget checked before lease (targets step, before INSERT chat_lease)',
     src.index('budget_check(ev[') < src.index('INSERT INTO bem_control.chat_lease'))
case('M15 start record S written in run() before lease and before mark_running',
     src.index("write_start_record(series, req['challenge'], ev)") < src.index('INSERT INTO bem_control.chat_lease')
     and bool(marks) and src.index("write_start_record(series, req['challenge'], ev)") < src.index('lease_mark_running('))

print(f'ZPROBE_B15_MARKRUNNING_TESTS {len(OK)}/{len(OK) + len(BAD)} {"PASS" if not BAD else "FAIL"}')
sys.exit(1 if BAD else 0)
