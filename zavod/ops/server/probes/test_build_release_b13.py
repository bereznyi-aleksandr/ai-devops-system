#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/test_build_release_b13.py
# ВЕРСИЯ: v0.3 (выпуск B13)  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-11-18 13:45 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-18 14:45 +02:00
# v0.3 (ошибка выпуска B13, приёмка шага на компьютере): T03 — 18 ключей кода, 3 ключа телефона и 3 ключа компьютера (pc_);
#   K01–K06 — pc_problem: положительный на HEAD и подмена каждого из трёх файлов компьютера; K07 — файлы компьютера не в
#   пакете (tar); S04 — в отпечатках 1+18+3+3 ключа;
#   M01–M02 — строка «Манифест для приёмки» называет zavod/ops/zprobe_pins_b13.txt, не zavod/ops/zprobe_pins.txt.
# v0.2 (после REL127): C01–C05 — файлы клетки (ключи кода бегунка) равны отпечаткам B10, телефонный zprobe_rules.py — те же
#   байты, что серверный; S01–S12 — M-355-REL127-01: настоящий tar пакета несёт все четыре файла телефона по путям проекта,
#   суммы трёх равны ключам отпечатков, файл отпечатков в tar — собранные отпечатки без суммы tar; отказ при отсутствии или
#   подмене любого; T03 — 18 ключей кода (без zprobe_pins_b9.txt) и 3 ключа телефона.
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
NEEDED = ([P + n for n in X.PROGRAMS + X.UNITS] + [X.PHONE_SERIES, X.PHONE_VERIFY, X.PHONE_RULES]
          + [X.CELL + k for k in X.CELL_KEYS] + [p for _, p in X.PC_KEYS] + sorted(X.PIN_FILES))
NEEDED = list(dict.fromkeys(NEEDED))
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
keys = [k for k, _ in X.B.PIN_KEYS]
case('T03_pin_keys', set(keys) == set(X.PROGRAMS) | set(X.UNITS) | set(X.CELL_KEYS) | {
    'phone_zprobe_series_b13.sh', 'phone_zprobe_verify.py', 'phone_zprobe_rules.py',
    'pc_zprobe_refs.sh', 'pc_zprobe_refs_check.py', 'pc_zprobe_rules.py'}
     and len(keys) == 12 + 2 + 4 + 3 + 3 and 'zprobe_pins_b9.txt' not in keys)
case('T04_release_and_all_phone_files_in_files', all(P + n in X.B.FILES for n in X.INSTALLER_CHAIN)
     and all(f in X.B.FILES for f in (X.PHONE_SERIES, X.PHONE_VERIFY, X.PHONE_RULES))
     and not any(f.startswith(X.CELL) for f in X.B.FILES))

# C: файлы клетки и телефонный rules
case('C01_cell_equals_b10_pins', X.cell_problem(head) is None)
for k in X.CELL_KEYS:
    g = tree({X.CELL + k: lambda b: b + b'\n# tampered\n'})
    case(f'C02_cell_{k}_tampered', X.cell_problem(g) is not None and X.source_problem(g) is not None)
case('C03_phone_rules_equal_server_and_b10', X.phone_rules_problem(head) is None
     and X.B.sha(head(X.PHONE_RULES)) == X.B.sha(head(P + 'zprobe_rules.py')))
g = tree({X.PHONE_RULES: lambda b: b + b'\n'})
case('C04_phone_rules_tampered', X.phone_rules_problem(g) is not None and X.source_problem(g) is not None)
g = tree({P + 'zprobe_rules.py': lambda b: b + b'\n'})
case('C05_server_rules_tampered_phone_differs', X.phone_rules_problem(g) is not None)

HEADC_M = subprocess.run(['git', '-C', ROOT, 'rev-parse', 'HEAD'], capture_output=True, check=True).stdout.decode().strip()
# K: файлы компьютера (три ключа pc_)
case('K01_pc_equal_b10_pins', X.pc_problem(head) is None and [k for k, _ in X.PC_KEYS] ==
     ['pc_zprobe_refs.sh', 'pc_zprobe_refs_check.py', 'pc_zprobe_rules.py'])
for k, pth in X.PC_KEYS:
    g = tree({pth: lambda b: b + b'\n# tampered\n'})
    case(f'K02_pc_{k}_tampered', X.pc_problem(g) is not None and X.source_problem(g) is not None)
case('K05_pins_b10_without_pc_key_refused',
     X.pc_problem(lambda p: head(p).replace(b'pc_zprobe_refs.sh ', b'xx_zprobe_refs.sh ') if p == X.B10_PINS else head(p)) is not None)

# M: строка «Манифест для приёмки» в отпечатках называет файл B13 (L-355-REL128-01)
_pt = X.B.pins_text(head, HEADC_M).decode('utf-8')
_mline = [ln for ln in _pt.splitlines() if 'Манифест для приёмки' in ln]
case('M01_manifest_comment_names_b13_path', len(_mline) == 1 and 'zavod/ops/zprobe_pins_b13.txt' in _mline[0])
case('M02_manifest_comment_not_old_path', 'zavod/ops/zprobe_pins.txt' not in _pt and 'zprobe_pins_b13.txt > manifest.txt' in _pt)

# S: пакет (tar) несёт все четыре файла телефона
import io  # noqa: E402
import tarfile  # noqa: E402
HEADC = subprocess.run(['git', '-C', ROOT, 'rev-parse', 'HEAD'], capture_output=True, check=True).stdout.decode().strip()
PINS, TAR, SH = X.B9B._build(ROOT, HEADC)


def retar(tar, drop=(), change=None):
    """Тот же tar без файлов drop и с подменённым содержимым change{путь: функция}."""
    out = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(tar)) as src, tarfile.open(fileobj=out, mode='w', format=tarfile.GNU_FORMAT) as dst:
        for m in src.getmembers():
            if m.name in drop:
                continue
            if m.isfile():
                b = src.extractfile(m).read()
                if change and m.name in change:
                    b = change[m.name](b)
                m.size = len(b)
                dst.addfile(m, io.BytesIO(b))
            else:
                dst.addfile(m)
    return out.getvalue()


FOUR = [X.PHONE_SERIES, X.PHONE_VERIFY, X.PHONE_RULES, X.B.PINS_PATH]
with tarfile.open(fileobj=io.BytesIO(TAR)) as _t:
    NAMES = set(_t.getnames())
    TARF = {m.name: _t.extractfile(m).read() for m in _t.getmembers() if m.isfile()}
want = X.B9B.parse(PINS)
case('S01_tar_has_all_four_phone_files_at_project_paths', all(p in NAMES for p in FOUR) and X.stage_problem(TAR, PINS) is None)
case('S02_three_phone_sums_equal_pins_keys', all(X.B.sha(TARF[p]) == want[k] for k, p in X.STAGE_PHONE))
case('S03_pins_in_tar_are_the_built_pins', TARF[X.B.PINS_PATH] == PINS and X.B.sha(PINS) == X.B.sha(TARF[X.B.PINS_PATH]))
case('S04_pins_carry_no_tar_or_sh_sum', X.B.sha(TAR) not in PINS.decode() and X.B.sha(SH) not in PINS.decode()
     and len(want) == 1 + 18 + 3 + 3)
for p in FOUR:
    case(f'S05_missing_{os.path.basename(p)}', X.stage_problem(retar(TAR, drop=(p,)), PINS) is not None)
for p in FOUR:
    case(f'S06_changed_{os.path.basename(p)}', X.stage_problem(retar(TAR, change={p: lambda b: b + b'\n'}), PINS) is not None)
case('S07_unreadable_tar', X.stage_problem(b'not a tar', PINS) is not None)
case('K06_pc_keys_in_pins_equal_files_and_not_in_tar', all(X.B.sha(head(p)) == want[k] for k, p in X.PC_KEYS)
     and not any(p in NAMES for k, p in X.PC_KEYS if p.startswith('zavod/ops/pc/')))

ok = all(RESULTS)
print(f'ZPROBE_BUILD_B13_TEST={"PASS" if ok else "FAIL"} cases={len(RESULTS)} tmp={TMP}')
sys.exit(0 if ok else 1)
