#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_codepins_b15.py
# ВЕРСИЯ: v0.1 (выпуск B15)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-19 15:43 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 15:43 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминал zavod (пускатель); автор, принять не может. Аудитор — ChatGPT.
# НАЗНАЧЕНИЕ: сквозная проверка отпечатков кода B15 — та же, что test_zprobe_codepins_b14.py v0.1, с именами B15:
#   отпечатки собирает сборщик B15 из коммита HEAD; на подставном корне сервера — байты выпуска по путям B15 (probes-b15,
#   службы -b15@); code_sha256 — от настоящей zprobe_runner.code_fingerprints() (бегунок B15: 20 файлов, в том числе
#   два новых модуля zprobe_start_status.py и zprobe_recstore.py); телефонная zprobe_verify.py читает собранный файл и
#   проверяет начало серии; путь --refs компьютера (ключи pc_). Отрицательные — изменён любой из 20 файлов, пропущен
#   или лишний ключ, набор B14 из 18 ключей (без двух новых модулей), старый набор из 11 ключей, чужой коммит.
#   Строки: CASE <имя> PASS|FAIL, итог ZPROBE_CODEPINS_B15_TEST=PASS|FAIL cases=N.
# ОГРАНИЧЕНИЯ: ничего не удаляет; пишет только в одну новую временную папку; сервер и телефон не нужны.
import hashlib
import importlib.util
import os
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_release_3_5_5_b15 as BB  # noqa: E402
import zprobe_runner as N  # noqa: E402

ROOT = subprocess.run(['git', '-C', HERE, 'rev-parse', '--show-toplevel'], capture_output=True, check=True).stdout.decode().strip()
HEADC = subprocess.run(['git', '-C', ROOT, 'rev-parse', 'HEAD'], capture_output=True, check=True).stdout.decode().strip()
P, B = BB.P, BB.B
RESULTS = []


def case(name, ok, why=''):
    RESULTS.append(bool(ok))
    print(f'CASE {name} {"PASS" if ok else "FAIL"}' + ('' if ok else f' :: {why}'))


def sha(b):
    return hashlib.sha256(b).hexdigest()


# Телефонная программа — файл из репозитория (рядом с ней лежит её zprobe_rules.py, тот же, что у сервера).
PHONE_FILE = os.path.join(ROOT, *BB.PHONE_VERIFY.split('/'))
sys.path.insert(0, os.path.dirname(PHONE_FILE))
spec = importlib.util.spec_from_file_location('phone_zprobe_verify', PHONE_FILE)
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)

# 1. Отпечатки — настоящий вызов сборщика на HEAD; читаются телефонной read_pins из файла.
PINS_BYTES, TAR, SH = BB.B9B._build(ROOT, HEADC)
TMP = tempfile.mkdtemp(prefix='b15codepins-')
PINS_FILE = os.path.join(TMP, 'zprobe_pins.txt')
with open(PINS_FILE, 'xb') as f:
    f.write(PINS_BYTES)
PINS = V.read_pins(PINS_FILE)

# 2. Подставной корень сервера: файлы выпуска по тем путям, где их ставит выпуск (программы B15 — LIB, службы — /etc,
#    клетка — как в B9/B10).
LIB = N.LIB
SERVER = {}
for n in BB.PROGRAMS:
    SERVER[LIB + '/' + n] = B.blob(ROOT, HEADC, P + n)
for n in BB.UNITS:
    SERVER['/etc/systemd/system/' + n] = B.blob(ROOT, HEADC, P + n)
for n, dest in (('zagent@.service', '/etc/systemd/system/'), ('zavod-proxy', '/usr/local/lib/zavod/'),
                ('zavod-gate', '/usr/local/lib/zavod/'), ('zavod-egress.nft', '/etc/zavod/')):
    SERVER[dest + n] = B.blob(ROOT, HEADC, BB.CELL + n)


def server_sha(over=None):
    files = dict(SERVER, **(over or {}))

    def f(p):
        p = p.replace('\\', '/')
        return sha(files[p if p.startswith('/') else LIB + '/' + p])
    return f


CH = '0123456789abcdef0123456789abcdef'
CL = {'status': 'SAFE', 'unit_active_after': 'inactive', 'load_state': 'masked', 'session_state': 'INTERRUPTED',
      'kept_copy': '/var/lib/zavod/probes/archive/s1/50-zprobe.conf', 'lease': 'a' * 32}
END = {'kind': 'SERIES_END', 'series': 's1', 'challenge': CH, 'status': 'COMPLETE', 'records': 1, 'cleanup': CL}
DIFF = 'code fingerprints differ from pins'
EARLY = (DIFF, 'release commit differs from pins', 'proxy health not confirmed')


def start_record(code, commit=None):
    return {'kind': 'SERIES_START', 'series': 's1', 'challenge': CH, 'code_sha256': code, 'probes': list(V.R.PROBES),
            'release': {'commit': commit or PINS['release_commit']}, 'control': {'proxy_health': 'OK'},
            'lease_state': 'INTERRUPTED'}


def verdict(code, commit=None):
    return V.series_check([start_record(code, commit), END], 's1', CH, PINS)


# Положительные
case('C01_pins_have_exactly_27_keys_read_by_phone_read_pins',
     len(PINS) == 1 + 20 + 3 + 3 and 'zprobe_pins_b9.txt' not in PINS and PINS['release_commit'] == HEADC, sorted(PINS))
CODE = N.code_fingerprints(server_sha())
case('C02_runner_PINNED_names_equal_pins_code_keys',
     set(CODE) == {k for k in PINS if k != 'release_commit' and not k.startswith(('phone_', 'pc_'))}
     and len(N.PINNED) == 20 and len(CODE) == 20)
case('C03_runner_fingerprints_equal_pins_values', all(PINS[k] == v for k, v in CODE.items()))
NEW15 = ('zprobe_start_status.py', 'zprobe_recstore.py')
case('C04_start_status_and_recstore_pinned_from_lib_b15',
     all(n in N.PINNED and n in CODE and PINS[n] == sha(SERVER[LIB + '/' + n]) for n in NEW15)
     and LIB == '/usr/local/lib/zavod/probes-b15'
     and all(PINS[n] == B.sha(B.blob(ROOT, HEADC, P + n)) for n in NEW15), str({n: PINS.get(n) for n in NEW15}))
res = verdict(CODE)
case('E01_clean_series_start_has_no_fingerprint_error', res != DIFF, res)
case('E02_clean_series_passes_the_start_gates_fingerprints_release_proxy', res not in EARLY, res)
case('E03_phone_programs_equal_pins', V.self_problem(PINS) is None, str(V.self_problem(PINS)))
case('E04_clean_end_to_end_result_has_no_pin_words',
     res is None or ('pins' not in res and 'fingerprint' not in res), res)

# Отрицательные: изменён один из 20 файлов выпуска на сервере
for k in sorted(CODE):
    path = next(p for p in N.PINNED if os.path.basename(p) == k)
    full = path if path.startswith('/') else LIB + '/' + path
    bad = N.code_fingerprints(server_sha({full: SERVER[full] + b'\n# tampered\n'}))
    case(f'N01_changed_{k}', verdict(bad) == DIFF, verdict(bad))
code = dict(CODE)
code.pop('zavod-gate')
case('N02_runner_misses_a_key_zavod-gate', verdict(code) == DIFF)
code = dict(CODE, **{'zprobe_pins_b9.txt': '0' * 64})
case('N03_runner_has_an_extra_key', verdict(code) == DIFF)
OLD11 = ('pb1_session.py', 'zprobe_rules.py', 'zprobe_runner.py', 'zprobe_journal.py', 'zprobe-start',
         'zprobe-run-b15@.service', 'zprobe-journal-b15@.service', 'zagent@.service', 'zavod-proxy', 'zavod-gate',
         'zavod-egress.nft')
case('N04_old_eleven_key_set_of_runner_v0.15_is_refused', verdict({k: v for k, v in CODE.items() if k in OLD11}) == DIFF)
case('N06_previous_eighteen_key_set_without_new_modules_is_refused',
     verdict({k: v for k, v in CODE.items() if k not in NEW15}) == DIFF)
case('N05_other_release_commit_refused_after_fingerprints_pass',
     verdict(CODE, 'f' * 40) == 'release commit differs from pins')
# Файл отпечатков B15 в репозитории: коды те же, что у собранных сейчас (программы не менялись после выпуска)
committed = os.path.join(ROOT, *B.PINS_PATH.split('/'))
if os.path.isfile(committed):
    cp = V.read_pins(committed)
    case('R01_committed_pins_code_keys_equal_fresh_build',
         {k: v for k, v in cp.items() if k != 'release_commit' and not k.startswith('pc_')}
         == {k: v for k, v in PINS.items() if k != 'release_commit' and not k.startswith('pc_')})
else:
    case('R01_committed_pins_absent_before_release_build', True)

# Путь --refs (приёмка шага на компьютере): в отпечатках должны быть pc_-ключи, иначе сумма программы снимков не найдена.
# Те же вызовы, что у телефона (zprobe_verify.verdict: R.refs_problem(..., pins.get('pc_zprobe_refs.sh'))) и у компьютера
# (zprobe_refs_check.problem). Снимки — формат zavod/ops/pc/zprobe_refs.sh (ZPROBE_REFS v2).
PCD = os.path.join(ROOT, 'zavod', 'ops', 'pc')
sys.path.insert(0, PCD)
import zprobe_refs_check as RC  # noqa: E402
TOOL = B.sha(B.blob(ROOT, HEADC, 'zavod/ops/pc/zprobe_refs.sh'))
SELF = B.sha(B.blob(ROOT, HEADC, 'zavod/ops/pc/zprobe_refs_check.py'))
RULES = B.sha(B.blob(ROOT, HEADC, P + 'zprobe_rules.py'))
RV = V.R
RUN = ['2026-11-12T21:10:00Z', '2026-11-12T21:20:00Z']


def snap(when, tool, t, series='s1'):
    return (f'ZPROBE_REFS v2\nwhen={when}\nseries={series}\nrepo={RV.REFS_REPO}\nprefix={RV.REFS_PREFIX}\n'
            f'tool_sha256={tool}\ntime_utc={t}\nrc=0\n---\n')


def refs_res(pins, tool=TOOL):
    return RV.refs_problem(snap('before', tool, '2026-11-12T21:05:00Z'), snap('after', tool, '2026-11-12T21:25:00Z'),
                           's1', CH, RUN, pins.get('pc_zprobe_refs.sh'))


WRONG = 'before snapshot made by a program not in pins'
case('F01_pins_have_pc_keys_equal_files', PINS.get('pc_zprobe_refs.sh') == TOOL and PINS.get('pc_zprobe_refs_check.py') == SELF
     and PINS.get('pc_zprobe_rules.py') == RULES, str({k: v for k, v in PINS.items() if k.startswith('pc_')}))
case('F02_refs_with_built_pins_and_tool_sha_accepted', refs_res(PINS) is None, str(refs_res(PINS)))
case('F03_refs_without_pc_key_refused_exactly', refs_res({k: v for k, v in PINS.items() if k != 'pc_zprobe_refs.sh'}) == WRONG)
case('F04_refs_foreign_tool_sum_refused_exactly', refs_res(PINS, 'e' * 64) == WRONG)
CPINS = os.path.join(TMP, 'pc_pins_read.txt')
with open(CPINS, 'xb') as f:
    f.write(PINS_BYTES)
TL = f'ZPROBE_TIMES series=s1 challenge={CH} run_start={RUN[0]} run_end={RUN[1]} pins_sha256={sha(PINS_BYTES)}'
cp = RC.read_pins(CPINS)
b4, a4 = snap('before', TOOL, '2026-11-12T21:05:00Z'), snap('after', TOOL, '2026-11-12T21:25:00Z')
case('F05_pc_check_accepts_built_pins', RC.problem(b4, a4, TL, cp, sha(PINS_BYTES), SELF, RULES) is None,
     str(RC.problem(b4, a4, TL, cp, sha(PINS_BYTES), SELF, RULES)))
case('F06_pc_check_refuses_other_self_or_rules',
     RC.problem(b4, a4, TL, cp, sha(PINS_BYTES), 'd' * 64, RULES) == 'zprobe_refs_check.py differs from pins'
     and RC.problem(b4, a4, TL, cp, sha(PINS_BYTES), SELF, 'd' * 64) == 'zprobe_rules.py differs from pins')
nopc = {k: v for k, v in cp.items() if not k.startswith('pc_')}
case('F07_pc_check_without_pc_keys_refused', RC.problem(b4, a4, TL, nopc, sha(PINS_BYTES), SELF, RULES) is not None)
case('F08_pc_keys_do_not_change_runner_code_set', len(CODE) == 20 and not any(k.startswith('pc_') for k in CODE))

ok = all(RESULTS)
print(f'ZPROBE_CODEPINS_B15_TEST={"PASS" if ok else "FAIL"} cases={len(RESULTS)} tmp={TMP}')
sys.exit(0 if ok else 1)
