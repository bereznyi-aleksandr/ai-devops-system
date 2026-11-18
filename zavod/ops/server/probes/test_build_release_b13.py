#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/test_build_release_b13.py
# ВЕРСИЯ: v0.1 (выпуск B13)  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-11-18 13:45 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-18 13:45 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминал zavod (пускатель); автор, принять не может.
# НАЗНАЧЕНИЕ: проверки источников сборщика B13 (build_release_3_5_5_b13.py): положительный случай на коммите HEAD
#   (суммы отпечатков B8–B12, модули без изменений, ACCEPTED, вхождения b10) и отрицательные на копиях файлов во
#   временной папке (подменённые байты модуля без изменений, изменённого модуля, лишнее «probes-b10» в программе,
#   изменённый файл отпечатков B12, чужой release_commit B12), сборка без установщика отказывает.
#   Строки: CASE <имя> PASS|FAIL. Итог: ZPROBE_BUILD_B13_TEST=PASS|FAIL. Установщик и сервер не нужны.
# ОГРАНИЧЕНИЯ: пишет только в новую временную папку; файлы репозитория не меняет; ничего не удаляет.
import os
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_release_3_5_5_b13 as X  # noqa: E402

ROOT = subprocess.run(['git', '-C', HERE, 'rev-parse', '--show-toplevel'], capture_output=True, check=True).stdout.decode().strip()
P = X.P
NEEDED = [P + n for n in X.PROGRAMS + X.UNITS] + [X.PHONE_SERIES, X.PHONE_VERIFY] + sorted(X.PIN_FILES)
RESULTS = []


def case(name, ok):
    RESULTS.append(ok)
    print(f'CASE {name} {"PASS" if ok else "FAIL"}')


head = lambda p: X.B.blob(ROOT, 'HEAD', p)  # noqa: E731
TMP = tempfile.mkdtemp(prefix='b13build-')
_n = [0]


def tree(mutate=None):
    """Новая папка с копиями нужных файлов HEAD (байты не меняются, кроме указанных); get читает из неё."""
    _n[0] += 1
    d = os.path.join(TMP, f't{_n[0]}')
    for p in NEEDED:
        b = head(p)
        if mutate and p in mutate:
            b = mutate[p](b)
        t = os.path.join(d, p)
        os.makedirs(os.path.dirname(t), exist_ok=True)
        with open(t, 'xb') as f:
            f.write(b)
    return lambda p: open(os.path.join(d, p), 'rb').read()


# положительные: текущий HEAD
case('P01_pins_files_known', X.pins_problem(head) is None)
case('P02_unchanged_equal_pins', X.unchanged_problem(head) is None)
case('P03_changed_accepted', X.accepted_problem(head) is None)
case('P04_no_unexpected_b10', X.b10_problem(head) is None)
case('P05_source_problem_none', X.source_problem(head) is None)
case('P06_same_on_copy', X.source_problem(tree()) is None)
case('P07_accepted_covers_changed_and_name_only',
     set(X.ACCEPTED) == {'zprobe_dropin.py', 'zprobe_runner.py', 'zprobe_export_rules.py', 'zprobe_checks.py',
                         'zprobe_journal.py', 'zprobe-start', 'zprobe_unstarted.py', 'zevidence_send.py'})
case('P08_unchanged_and_changed_are_all_12', set(X.ACCEPTED) | set(X.UNCHANGED) == set(X.PROGRAMS))

# отрицательные
for n in X.UNCHANGED:
    g = tree({P + n: lambda b: b + b'\n# tampered\n'})
    case(f'N01_unchanged_{n}_tampered', X.unchanged_problem(g) is not None and X.source_problem(g) is not None)
g = tree({X.PHONE_VERIFY: lambda b: b + b'\n'})
case('N02_phone_verify_tampered', X.unchanged_problem(g) is not None)
for n in sorted(X.ACCEPTED):
    g = tree({P + n: lambda b: b + b'\n# tampered\n'})
    case(f'N03_changed_{n}_tampered', X.accepted_problem(g) is not None and X.source_problem(g) is not None)
g = tree({P + 'zprobe_runner.py': lambda b: b + b'\nLIB = "/usr/local/lib/zavod/probes-b10"\n'})
case('N04_extra_probes_b10_in_program', X.b10_problem(g) is not None and 'probes-b10' in X.b10_problem(g))
g = tree({P + 'zprobe-run-b13@.service': lambda b: b + b'\nExecStopPost=/bin/true zprobe-journal-b10@%i\n'})
case('N05_journal_b10_in_service', X.b10_problem(g) is not None and 'journal-b10@' in X.b10_problem(g))
g = tree({P + 'zprobe_checks.py': lambda b: b + b'\nA = "zprobe-run-b10@"\nB = "zprobe-run-b10@"\n'})
case('N06_second_foreign_unit_in_checks', X.b10_problem(g) is not None)
g = tree({P + 'zprobe_checks.py': lambda b: b + b'\n# probes-b10 only in comment\n'})
case('N07_comment_line_is_not_a_finding', X.b10_problem(g) is None)
for pf in ('zavod/ops/zprobe_pins_b8.txt', 'zavod/ops/zprobe_pins_b9.txt', 'zavod/ops/zprobe_pins_b10.txt',
           'zavod/ops/zprobe_pins_b11.txt', 'zavod/ops/zprobe_pins_b12.txt'):
    g = tree({pf: lambda b: b + b'# x\n'})
    case(f'N08_pins_file_{os.path.basename(pf)}_changed', X.pins_problem(g) is not None and X.source_problem(g) is not None)
g = tree({X.B12_PINS: lambda b: b.replace(X.B12_RELEASE_COMMIT.encode(), b'0' * 40)})
case('N09_b12_pins_changed_commit', X.pins_problem(g) is not None)
try:
    X.source_problem(lambda p: head(p) if p != P + 'zprobe_seal.py' else open(os.path.join(TMP, 'absent'), 'rb').read())
    missing = False
except OSError:
    missing = True
case('N10_missing_file_not_silently_ok', missing)

# сборка без установщика честно отказывает (его ещё нет), а не молча собирает
try:
    X.build(ROOT, subprocess.run(['git', '-C', ROOT, 'rev-parse', 'HEAD'], capture_output=True, check=True).stdout.decode().strip())
    built = True
except SystemExit as e:
    built = False
    msg = str(e)
has_installer = subprocess.run(['git', '-C', ROOT, 'cat-file', '-e', 'HEAD:' + P + 'zprobe_release_b13.py']).returncode == 0
case('B01_build_refuses_without_installer', (not built and msg.startswith('RELEASE_REFUSED git show')) or has_installer)

# шаблон .sh — B13
t = X.B.SH_TEMPLATE
case('T01_template_b13', 'zprobe_release_b13.py" "$M"' in t and 'probes-b13' in t and 'b12' not in t.lower())
case('T02_constants', X.B.VERSION == '3.5.5-b13' and X.B.PINS_PATH.endswith('zprobe_pins_b13.txt')
     and X.B.SH_PATH.endswith('zprobe-release-3.5.5-b13.sh') and len(X.PROGRAMS) == 12 and len(X.UNITS) == 2)
case('T03_pin_keys', {k for k, _ in X.B.PIN_KEYS} >= {'phone_zprobe_series_b13.sh', 'phone_zprobe_verify.py',
                                                       'phone_zprobe_rules.py', 'zprobe_pins_b9.txt'} and len(X.B.PIN_KEYS) == 12 + 2 + 1 + 3)
case('T04_release_files_in_files', all(P + n in X.B.FILES for n in X.INSTALLER_CHAIN) and X.PHONE_SERIES in X.B.FILES)

ok = all(RESULTS)
print(f'ZPROBE_BUILD_B13_TEST={"PASS" if ok else "FAIL"} cases={len(RESULTS)} tmp={TMP}')
sys.exit(0 if ok else 1)
