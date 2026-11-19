#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_b15_budget.py
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-19 11:48 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 11:48 +02:00
# ИСПОЛНИТЕЛЬ: Claude (терминал zavod, пускатель)
# НАЗНАЧЕНИЕ: проверки бюджета B15 (REL148 M-02: предел прямого git push 150–180 с; разбор pb1trial4 — повторы SYN
#   ~127 с на адрес). Заменяет для B15 проверку M01 из test_zprobe_b14_markrunning.py (там закреплено 831 с B14;
#   B14-файл не правится). Остальные проверки M02–M14 B14 остаются в силе и для B15.
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zprobe_runner as N  # noqa: E402
import zprobe_rules as R  # noqa: E402
import pb1_session as S  # noqa: E402

OK, BAD = [], []


def case(name, cond):
    (OK if cond else BAD).append(name)
    print(('PASS ' if cond else 'FAIL ') + name, flush=True)


case('B01 budget formula 13 targets, 8 names = 951 s', N.collect_budget(13, 8) == 951)
case('B02 direct push limit within REL148 range 150..180 s', 150 <= N.DIRECT_PUSH_S <= 180)
case('B03 session and runner use the same direct push limit', S.DIRECT_PUSH_S == N.DIRECT_PUSH_S)
case('B04 direct limit covers measured SYN retries 127 s', N.DIRECT_PUSH_S >= 127 + 10)
case('B05 B15 budget = B14 budget + (direct - 60)', N.collect_budget(13, 8) == 831 + (N.DIRECT_PUSH_S - 60))
big = N.collect_budget(R.MAX_TARGETS, len(R.GH_NAMES))
try:
    N.budget_check(big, 300)
    fits = True
except N.Abort:
    fits = False
case('B06 MAX_TARGETS budget fits TimeoutStartSec with 300 s elapsed', fits)

print(f'ZPROBE_B15_BUDGET_TESTS {len(OK)}/{len(OK) + len(BAD)} ' + ('PASS' if not BAD else 'FAIL'))
sys.exit(1 if BAD else 0)
