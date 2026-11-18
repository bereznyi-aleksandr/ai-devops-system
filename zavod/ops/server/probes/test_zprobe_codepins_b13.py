#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_codepins_b13.py
# ВЕРСИЯ: v0.1 (выпуск B13)  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-11-18 14:27 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-18 14:27 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминал zavod (пускатель); автор, принять не может. Аудитор — ChatGPT.
# НАЗНАЧЕНИЕ: СКВОЗНАЯ проверка ошибки выпуска B13 («набор отпечатков кода, который пишет бегунок, не совпадает с файлом
#   отпечатков»): отпечатки собираются сборщиком B13 из коммита HEAD (настоящий вызов); на подставном корне сервера лежат
#   байты выпуска по тем путям, где их ставит выпуск; запись начала серии получает code_sha256 от настоящей функции бегунка
#   zprobe_runner.code_fingerprints(); телефонная программа zprobe_verify.py (её read_pins и series_check) читает собранный
#   файл отпечатков и проверяет начало серии. Положительный случай: ошибки «code fingerprints differ from pins» нет и
#   ворота начала (номер выпуска, проверка прокси, состояние аренды) пройдены. Отрицательные: изменён любой из 18
#   файлов, пропущен или лишний ключ — ровно эта ошибка. Строки: CASE <имя> PASS|FAIL, итог
#   ZPROBE_CODEPINS_B13_TEST=PASS|FAIL cases=N.
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
import build_release_3_5_5_b13 as BB  # noqa: E402
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
TMP = tempfile.mkdtemp(prefix='b13codepins-')
PINS_FILE = os.path.join(TMP, 'zprobe_pins.txt')
with open(PINS_FILE, 'xb') as f:
    f.write(PINS_BYTES)
PINS = V.read_pins(PINS_FILE)

# 2. Подставной корень сервера: файлы выпуска по тем путям, где их ставит выпуск (программы B13 — LIB, службы — /etc,
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
case('C01_pins_have_exactly_22_keys_read_by_phone_read_pins',
     len(PINS) == 1 + 18 + 3 and 'zprobe_pins_b9.txt' not in PINS and PINS['release_commit'] == HEADC, sorted(PINS))
CODE = N.code_fingerprints(server_sha())
case('C02_runner_PINNED_names_equal_pins_code_keys',
     set(CODE) == {k for k in PINS if k != 'release_commit' and not k.startswith(('phone_', 'pc_'))}
     and len(N.PINNED) == 18 and len(CODE) == 18)
case('C03_runner_fingerprints_equal_pins_values', all(PINS[k] == v for k, v in CODE.items()))
res = verdict(CODE)
case('E01_clean_series_start_has_no_fingerprint_error', res != DIFF, res)
case('E02_clean_series_passes_the_start_gates_fingerprints_release_proxy', res not in EARLY, res)
case('E03_phone_programs_equal_pins', V.self_problem(PINS) is None, str(V.self_problem(PINS)))
case('E04_clean_end_to_end_result_has_no_pin_words',
     res is None or ('pins' not in res and 'fingerprint' not in res), res)

# Отрицательные: изменён один из 18 файлов выпуска на сервере
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
         'zprobe-run-b13@.service', 'zprobe-journal-b13@.service', 'zagent@.service', 'zavod-proxy', 'zavod-gate',
         'zavod-egress.nft')
case('N04_old_eleven_key_set_of_runner_v0.15_is_refused', verdict({k: v for k, v in CODE.items() if k in OLD11}) == DIFF)
case('N05_other_release_commit_refused_after_fingerprints_pass',
     verdict(CODE, 'f' * 40) == 'release commit differs from pins')
# Файл отпечатков B13 в репозитории: коды те же, что у собранных сейчас (программы не менялись после выпуска)
committed = os.path.join(ROOT, *B.PINS_PATH.split('/'))
if os.path.isfile(committed):
    cp = V.read_pins(committed)
    case('R01_committed_pins_code_keys_equal_fresh_build',
         {k: v for k, v in cp.items() if k != 'release_commit'} == {k: v for k, v in PINS.items() if k != 'release_commit'})
else:
    case('R01_committed_pins_absent_before_release_build', True)

ok = all(RESULTS)
print(f'ZPROBE_CODEPINS_B13_TEST={"PASS" if ok else "FAIL"} cases={len(RESULTS)} tmp={TMP}')
sys.exit(0 if ok else 1)
