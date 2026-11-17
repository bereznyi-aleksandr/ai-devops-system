#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_r2_b12.py
# ВЕРСИЯ: v0.2 (выпуск B12)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-17 22:12 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-17 22:30 +02:00 (v0.2: R01b — сумма proof в строке R2 сверяется с байтами файла, B11 и B12 различаются из-за tool_version; R03b — закрепка в порядке collect; подробный вывод R01b)
# ИСПОЛНИТЕЛЬ: Claude, терминальный чат zavod (сменщик после 80d67696)
# НАЗНАЧЕНИЕ: проверки проекта DESIGN_B12_H4_DIAG v0.3 (REL109 AGREED 0/0/2) — R01–R12 раздела 3 и R13 (тесты R B11 на
#   коде B12). Эталон B11 — копии ref_b11/zprobe_checks_b11.py.txt (6311c58c…) и ref_b11/zprobe_r2_b11.py.txt (923c8b62…),
#   суммы сверяются. Сбор фактов collect проверяется на подставной системе (journalctl, systemctl, psql, /proc — подмена
#   внутри процесса). Чистые случаи — без root, любая ОС; main() R2 — только Linux root (в CI sudo).
#   REL109 L-02: R08 разбирает КАЖДУЮ полную строку R2_DIAG исправного канала; законное отсутствие строки (ранний отказ,
#   обрыв stdout) проверяется отдельно в R04 и R12 и успешной диагностикой не считается.
#   Строки: CASE <Rnn_имя> PASS|FAIL|SKIP. Итог: ZPROBE_R2_B12_TEST=PASS | PASS_NO_ROOT | FAIL.
# ОГРАНИЧЕНИЯ: пишет только во временные папки; ничего не удаляет; подмены — только внутри процесса теста.
import contextlib
import copy
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import types

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_zprobe_export as TX  # noqa: E402
import test_zprobe_r2 as T2  # noqa: E402
import zprobe_checks as C  # noqa: E402
import zprobe_r2 as R2  # noqa: E402
import zprobe_unstarted as UN  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):                 # фикстуры test_zprobe_checks.py (его K/B идут отдельно)
    import test_zprobe_checks as TC  # noqa: E402

OK, ROOT = True, TX.ROOT
B11_C_SHA = '6311c58c6d8811e371a7821eaa2c1cd08c54794a0de5e06892624bf5ff19b54b'
B11_R_SHA = '923c8b62ef386c09508c20efd92885cad72c1683b7626a4ddf00901e8c72abf1'
TEST_PIN, TEST_PIN_SHA = TC.TP, TC.H('test-pin')
DIAGS = []                                   # все полные строки R2_DIAG исправного канала — для R08
HEX64 = re.compile(r'[0-9a-f]{64}')


def case(name, cond, detail=''):
    global OK
    OK &= bool(cond)
    print('CASE', name, 'PASS' if cond else 'FAIL ' + f'-> {detail}'[:400], flush=True)


def skip(name):
    print('CASE', name, 'SKIP (needs Linux root)', flush=True)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def load_b11():
    """Эталон B11: zprobe_checks и zprobe_r2 из копий выпуска B11 (суммы сверяются); R2 B11 видит проверки B11."""
    rc = open(os.path.join(HERE, 'ref_b11', 'zprobe_checks_b11.py.txt'), 'rb').read()
    rr = open(os.path.join(HERE, 'ref_b11', 'zprobe_r2_b11.py.txt'), 'rb').read()
    mc = types.ModuleType('zprobe_checks_b11')
    mc.__file__ = os.path.join(HERE, 'zprobe_checks_b11.py')
    exec(compile(rc, 'zprobe_checks_b11.py', 'exec'), mc.__dict__)
    keep = sys.modules['zprobe_checks']
    sys.modules['zprobe_checks'] = mc
    try:
        mr = types.ModuleType('zprobe_r2_b11')
        mr.__file__ = os.path.join(HERE, 'zprobe_r2_b11.py')
        exec(compile(rr, 'zprobe_r2_b11.py', 'exec'), mr.__dict__)
    finally:
        sys.modules['zprobe_checks'] = keep
    return mc, mr, sha(rc) == B11_C_SHA and sha(rr) == B11_R_SHA and mr.C is mc


MC, MR, B11_OK = load_b11()


class Pin:
    """Пробный PIN (как в test_zprobe_checks.py) — в проверках B12 и B11 одновременно."""
    def __enter__(self):
        self.keep = [(m, m.PIN_B9, m.PIN_SHA) for m in (C, MC)]
        for m in (C, MC):
            m.PIN_B9, m.PIN_SHA = TEST_PIN, TEST_PIN_SHA

    def __exit__(self, *a):
        for m, p, s in self.keep:
            m.PIN_B9, m.PIN_SHA = p, s


def pinned(**kw):
    f = TC.facts('b9')
    TC.alt(f, **kw)
    return f


def no_diag(ev):
    return {k: v for k, v in ev.items() if k != 'diag'}


# ---------------------------------------------------------------------------------------------------------------
# Набор фактов для регрессии B11↔B12: базовые (b9 строгий, b10, b9 закреплённый) и все отрицательные B08–B20, плюс каждый
# ключ верхнего уровня, scan, journald_restart, lease_row, anchor — удалён и заменён значением неверного типа.
BAD = (None, 'x', 7, -1, 0, True, False, [], {}, 1.5, ['x'], {'a': 1})


def corpus():
    gap = [e for e in TC.ENT if int(e['__SEQNUM']) != 1003]
    out = [('b9', TC.facts('b9')), ('b10', TC.facts('b10')), ('pin', pinned()), ('gap', pinned(ents=gap)),
           ('dup', pinned(ents=TC.ENT + [TC.ENT[3]])), ('first_lost', pinned(ents=TC.ENT[1:])),
           ('seventh', pinned(oe=TC.OED + [TC.oed(dict(TC.SELF[0], MESSAGE='x'))], other=7)),
           ('missing', pinned(oe=TC.OED[:5], other=5)), ('zero_other', pinned(oe=[], other=0))]
    for tag, mut in (('mono1', lambda f: f.update(journald_mono_us=f['journald_mono_us'] + 1000000)),
                     ('pid', lambda f: f['journald_restart'].update(main_pid='4243')),
                     ('pids', lambda f: f['journald_restart'].update(pids=['5', '77', '4242'])),
                     ('rx0', lambda f: f['journald_restart'].update(rx=0)),
                     ('rxN', lambda f: f['journald_restart'].update(rx=None)),
                     ('gap61', lambda f: f.update(first_entry_s=f['btime'] + 61)),
                     ('v1', lambda f: f.update(verify_rc=1)), ('v124', lambda f: f.update(verify_rc=124)),
                     ('scan1', lambda f: f['scan'].update(rc=1)), ('loss1', lambda f: f['scan'].update(loss=1)),
                     ('jact', lambda f: f.update(journald_active='failed')),
                     ('series', lambda f: f.update(series='pb1trial3')), ('fmt', lambda f: f.update(fmt='b10'))):
        g = pinned()
        mut(g)
        out.append((tag, g))
    for tag, f in list(out[:3]):
        for k in sorted(f):
            g = copy.deepcopy(f)
            del g[k]
            out.append((f'{tag}-{k}', g))
            for i, bad in enumerate(BAD):
                g = copy.deepcopy(f)
                g[k] = copy.deepcopy(bad)
                out.append((f'{tag}-{k}={i}', g))
        for sub in ('scan', 'journald_restart', 'lease_row', 'anchor'):
            for k in sorted(f.get(sub) or {}):
                for i, bad in enumerate(BAD):
                    g = copy.deepcopy(f)
                    g[sub][k] = copy.deepcopy(bad)
                    out.append((f'{tag}-{sub}.{k}={i}', g))
    return out


# ---------------------------------------------------------------------------------------------------------------
# Подставная система для collect (журнал, systemctl, psql, /proc): коды проходов и ответ journalctl --verify задаются.
class FakeSys:
    def __init__(self, rc3=0, rp=0, rr=0, scan_rc=0, rq=0, loss=0, verify=('rc', 0, b''), fe_gap=2):
        self.rc3, self.rp, self.rr, self.scan_rc, self.rq, self.loss = rc3, rp, rr, scan_rc, rq, loss
        self.verify, self.fe_gap = verify, fe_gap
        self.base = pinned()

    def open(self, path, *a, **k):
        if path == '/proc/sys/kernel/random/boot_id':
            b = self.base['boot_now']
            return io.StringIO(f'{b[:8]}-{b[8:12]}-{b[12:16]}-{b[16:20]}-{b[20:]}\n')
        if path == '/proc/stat':
            return io.StringIO(f"cpu 1 2 3\nbtime {self.base['btime']}\n")
        raise FileNotFoundError(path)

    def psql(self, sql, **kw):
        if 'chat_lease' in sql:
            return json.dumps(self.base['lease_row'])
        return json.dumps(self.base['db'])

    def show(self, unit, *props):
        if unit == 'systemd-journald.service':
            if 'MainPID' in props:
                return {'MainPID': '4242'}
            return {'ActiveState': 'active', 'ExecMainStartTimestampMonotonic': str(self.base['journald_mono_us'])}
        return {'FragmentPath': ''}

    def read_json_at(self, path, limit=0):
        return {'state': (self.base['state'], 'f' * 64), 'evidence': ({'lease': TC.L}, 'e' * 64),
                'anchor': (self.base['anchor'], 'a' * 64)}.get(os.path.basename(path).split('.')[0], (None, None))

    def stream(self, args, each, timeout=600):
        if args[0] == '-u':
            return 0, 0, None
        if args[0].startswith('--cursor='):
            cur = args[0].split('=', 1)[1]
            each({'__CURSOR': cur})
            return 0, 1, cur
        if 'SYSLOG_IDENTIFIER=systemd-journald' in args:
            for p in ('77', '4242'):
                each({'_PID': p})
            return self.rp, 2, None
        if '_PID=1' in args:
            each({'MESSAGE': 'Reexecuting.'})
            return self.rr, 1, None
        if '--until' in args:
            if self.rc3 == 0:
                each({'__REALTIME_TIMESTAMP': str((self.base['btime'] + self.fe_gap) * 1000000)})
            return self.rc3, 1, None
        if args == ['-b', '0']:
            for e in TC.ENT:
                each(e)
            return self.rq, len(TC.ENT), None
        ents = [{'__CURSOR': TC.CUR_F, 'MESSAGE': 'a'}] + [{'SYSLOG_IDENTIFIER': 'systemd-journald',
                                                             'MESSAGE': 'Missed 3 kernel messages'}] * self.loss
        for e in ents:
            each(e)
        return self.scan_rc, len(ents), TC.CUR_L

    def run(self, args, **kw):
        kind = self.verify[0]
        if kind == 'oserror':
            raise OSError(5, 'journalctl io')
        if kind == 'timeout':
            raise subprocess.TimeoutExpired(args, 120, stderr=self.verify[2])
        return types.SimpleNamespace(returncode=self.verify[1], stderr=self.verify[2], stdout=b'')

    @contextlib.contextmanager
    def on(self, *mods):
        names = ('open', 'psql_stdin', 'show', 'read_json_at', 'journal_stream', 'subprocess', 'svc_mask', 'os')
        osx = types.SimpleNamespace(**{k: getattr(os, k) for k in dir(os) if not k.startswith('__')})
        osx.O_NOFOLLOW, osx.O_CLOEXEC = getattr(os, 'O_NOFOLLOW', 0), getattr(os, 'O_CLOEXEC', 0)   # Windows: без флагов
        keep = [(m, n, m.__dict__.get(n, KeyError)) for m in mods for n in names]
        fake = {'open': self.open, 'psql_stdin': self.psql, 'show': self.show, 'read_json_at': self.read_json_at,
                'journal_stream': self.stream,
                'subprocess': types.SimpleNamespace(run=self.run, TimeoutExpired=subprocess.TimeoutExpired),
                'svc_mask': lambda unit: {'svc': self.base['svc'], 'mask': self.base['mask']}, 'os': osx}
        for m in mods:
            for n in names:
                setattr(m, n, fake[n])
        try:
            yield
        finally:
            for m, n, v in keep:
                if v is KeyError:
                    delattr(m, n)
                else:
                    setattr(m, n, v)


SRC = {'state': '/x/state.json', 'evidence': '/x/evidence.json', 'anchor': '/x/anchor.json',
       'manifest_state_sha': 'f' * 64, 'fragment_expected': None}


def fake_collect(m=None, **kw):
    fs = FakeSys(**kw)
    m = m or C
    with Pin(), fs.on(m):
        return m.collect('b9', 'pb1trial2', TC.LID, SRC)


# ---------------------------------------------------------------------------------------------------------------
def check_schema(line):
    """R08: строка R2_DIAG — json.loads и закрытая схема (ключи и типы)."""
    if not line.startswith('R2_DIAG ') or '\n' in line:
        return False
    o = json.loads(line.split(' ', 1)[1])
    if not isinstance(o, dict) or o.get('v') != 1 or o.get('state') not in R2.DIAG_STATES:
        return False
    if 'error' in o:
        return set(o) == {'v', 'state', 'error', 'len'} and o['error'] == 'OVERSIZE' and type(o['len']) is int
    if o['state'] == 'DIAG_ERROR':
        return set(o) == {'v', 'state', 'code'} and o['code'] in R2.DIAG_CODES
    if set(o) != set(R2.DIAG_KEYS):
        return False

    def hx(v):
        return v is None or (isinstance(v, str) and bool(HEX64.fullmatch(v)))

    def bi(d, keys, ints, strs=None):
        return d is None or (isinstance(d, dict) and set(d) == set(keys) and all(
            v is None or (type(v) is int if k in ints else (v in strs[k] if strs and k in strs else type(v) is bool))
            for k, v in d.items()))
    return (o['code'] is None or o['code'] in R2.DIAG_CODES) and o['origin'] in (None, R2.ORIGIN) \
        and isinstance(o['failed'], list) and all(x in R2.FAILED_NAMES + ('OTHER',) for x in o['failed']) \
        and bi(o['ok'], C.CHECKS, ()) and bi(o['H4'], C.H4_PARTS, C.H4_INTS) \
        and bi(o['jdiag'], C.JDIAG_KEYS, tuple(k for k in C.JDIAG_KEYS if k != 'verify_class'),
               {'verify_class': C.VERIFY_CLASSES}) \
        and hx(o['obs_sha']) and hx(o['facts_sha']) and hx(o['derived_eval_sha']) \
        and (o['state'] == 'PRIMARY_CHECKS') == (o['origin'] == R2.ORIGIN) \
        and (o['state'] == 'PRIMARY_CHECKS' or (o['H4'] is None and o['jdiag'] is None and o['ok'] is None))


def dl(r, box):
    line = R2.diag_line(r, box)
    DIAGS.append(line)
    return line, json.loads(line.split(' ', 1)[1])


def kept_box(f):
    return {'facts': f, 'facts_sha': R2.facts_sha(f), 'kept': ('/k/obs.json', sha(C.obs_json(f).encode('ascii')))}


def pure():
    case('R00_b11_reference_copies_and_versions', B11_OK and R2.TOOL_VERSION == 'zprobe-r2-b12-0.1.checks-0.7'
         and len(R2.TOOL_VERSION) <= 40 and R2.PATHS['pins_b9'] == '/usr/local/lib/zavod/probes-b12/zprobe_pins_b9.txt'
         and open(os.path.join(HERE, 'zprobe_checks.py'), encoding='utf-8').read().split('\n')[2].startswith(
             '# ВЕРСИЯ: v0.7 (выпуск B12)'), (B11_OK, R2.TOOL_VERSION))
    # R01/R02 — регрессия B11↔B12 на всём наборе фактов (настоящий PIN и пробный)
    bad, n, inv = [], 0, []
    for pin in (False, True):
        with (Pin() if pin else contextlib.nullcontext()):
            for tag, f in corpus():
                f11, f12 = copy.deepcopy(f), copy.deepcopy(f)
                e11, e12 = MC.evaluate(f11), C.evaluate(f12)
                n += 1
                same = no_diag(e12) == e11 and f11 == f12 == f
                if same and e11.get('ok'):
                    same = MC.proof_checks(e11) == C.proof_checks(e12)
                if same and e11.get('failed') != ['ARGS']:
                    d = e12['diag']['H4']
                    same = set(d) == set(C.H4_PARTS) and all(
                        v is None or (type(v) is int if k in C.H4_INTS else type(v) is bool) for k, v in d.items())
                    formula = d['h4a'] and (d['h4b'] or d['alt']) and d['h4c'] and d['verify_ok']
                    if e12['checks']['H4']['ok'] != bool(formula) or d['h4c'] != (d['h4c_scan_ok'] and d['h4c_loss_ok']):
                        inv.append(tag)
                elif same:
                    same = 'diag' not in e12
                if not same:
                    bad.append((pin, tag))
                if MC.obs_json(f) != C.obs_json(f):
                    bad.append(('obs', pin, tag))
    case('R01_evaluate_b11_b12_identical_except_diag', not [b for b in bad if b[0] != 'obs'] and n > 1000 and not inv,
         (n, bad[:5], inv[:5]))
    case('R02_obs_json_b11_b12_identical', not [b for b in bad if b[0] == 'obs'], bad[:5])
    # R03 — совместные состояния частей H4 (на закреплённых фактах; ожидается ВЕСЬ набор частей)
    base = {'h4a': True, 'h4b': False, 'alt': True, 'h4c': True, 'h4c_scan_ok': True, 'h4c_loss_ok': True,
            'verify_ok': True, 'pin': True, 'seq_ok': True, 'a_jact': True, 'a_start': True, 'a_pid': True,
            'a_pids': True, 'a_rx': True, 'jd_start_obs': TC.T0 + 500, 'jd_start_pin': TC.T0 + 500, 'T0': TC.T0}
    rows = (('none', lambda f: None, {}),
            ('fe_null', lambda f: f.update(first_entry_s=None), {'h4a': False}),
            ('fe_late', lambda f: f.update(first_entry_s=f['btime'] + 61), {'h4a': False}),
            ('scan_rc', lambda f: f['scan'].update(rc=1), {'h4c_scan_ok': False, 'h4c': False}),
            ('loss', lambda f: f['scan'].update(loss=1), {'h4c_loss_ok': False, 'h4c': False}),
            ('scan_rc_loss', lambda f: f['scan'].update(rc=1, loss=1),
             {'h4c_scan_ok': False, 'h4c_loss_ok': False, 'h4c': False}),
            ('loss_null', lambda f: f['scan'].update(loss=None), {'h4c_loss_ok': False, 'h4c': False}),
            ('verify1', lambda f: f.update(verify_rc=1), {'verify_ok': False}),
            ('verify124', lambda f: f.update(verify_rc=124), {'verify_ok': False}),
            ('jact', lambda f: f.update(journald_active='failed'), {'a_jact': False, 'alt': False}),
            ('mono', lambda f: f.update(journald_mono_us=f['journald_mono_us'] + 1000000),
             {'a_start': False, 'alt': False, 'jd_start_obs': TC.T0 + 501}),
            ('pid', lambda f: f['journald_restart'].update(main_pid='1'), {'a_pid': False, 'alt': False}),
            ('pids', lambda f: f['journald_restart'].update(pids=['1']), {'a_pids': False, 'alt': False}),
            ('pids_null', lambda f: f['journald_restart'].update(pids=None), {'a_pids': False, 'alt': False}),
            ('rx0', lambda f: f['journald_restart'].update(rx=0), {'a_rx': False, 'alt': False}),
            ('rx_null', lambda f: f['journald_restart'].update(rx=None), {'a_rx': False, 'alt': False}),
            ('gap', lambda f: TC.alt(f, [e for e in TC.ENT if int(e['__SEQNUM']) != 1003]),
             {'seq_ok': False, 'alt': False}),
            ('t0', lambda f: f['lease_row'].update(opened_at_s=TC.T0 + 1),
             {'pin': False, 'seq_ok': False, 'alt': False, 'T0': TC.T0 + 1}),
            ('fe_null_and_verify', lambda f: f.update(first_entry_s=None, verify_rc=1), {'h4a': False, 'verify_ok': False}))
    bad3 = []
    with Pin():
        for tag, mut, over in rows:
            f = pinned()
            mut(f)
            ev = C.evaluate(f)
            want = dict(base, **over)
            d = ev['diag']['H4']
            formula = want['h4a'] and (want['h4b'] or want['alt']) and want['h4c'] and want['verify_ok']
            if d != want or ev['checks']['H4']['ok'] != formula:
                bad3.append((tag, {k: (d.get(k), want[k]) for k in want if d.get(k) != want[k]}))
        strict = C.evaluate(TC.facts('b9'))['diag']['H4']
    case('R03a_h4_parts_joint_states_full_set', not bad3 and strict['h4b'] is True and strict['alt'] is False
         and strict['seq_ok'] is False and strict['a_start'] is False, (bad3[:3], strict))
    # R03b — jdiag из collect на подставной системе (коды и длительности проходов, verify без текста)
    out = {}
    for tag, kw in (('ok', {}), ('rc3', {'rc3': 1}), ('rp', {'rp': 1}), ('rr', {'rr': 1}), ('scan', {'scan_rc': 124}),
                    ('loss', {'loss': 2}), ('rq', {'rq': 98}), ('vnz', {'verify': ('rc', 1, b'a\n\n  \nb\nc\n')}),
                    ('vto', {'verify': ('timeout', 0, b'x\ny\n')})):
        out[tag] = fake_collect(**kw)
    j = {k: v['jdiag'] for k, v in out.items()}
    ms_ok = all(type(x[k]) is int and x[k] >= 0 for x in j.values() for k in ('ms3', 'msp', 'msr', 'ms_scan', 'ms_seq',
                                                                               'verify_ms'))
    base_j = {'rc3': 0, 'first_entry_s': TC.T0 - 3600 + 2, 'btime': TC.T0 - 3600, 'rp': 0, 'rr': 0, 'scan_rc': 0,
              'scan_loss': 0, 'rq': 0, 'verify_class': 'OK', 'verify_rc': 0, 'verify_err_lines': 0, 'verify_err_bytes': 0}
    parts = (set(j['ok']) == set(C.JDIAG_KEYS), ms_ok, all(j['ok'][k] == v for k, v in base_j.items()),
             j['rc3']['rc3'] == 1 and j['rc3']['first_entry_s'] is None and out['rc3']['first_entry_s'] is None,
             j['rp']['rp'] == 1 and out['rp']['journald_restart']['pids'] is None,
             j['rr']['rr'] == 1 and out['rr']['journald_restart']['rx'] is None,
             j['scan']['scan_rc'] == 124 and out['scan']['scan']['rc'] == 124,
             j['loss']['scan_loss'] == 2 and out['loss']['scan']['loss'] == 2,
             j['rq']['rq'] == 98 and out['rq']['scan']['seq'] is None,
             j['vnz']['verify_class'] == 'NONZERO' and j['vnz']['verify_rc'] == 1 and out['vnz']['verify_rc'] == 1
             and j['vnz']['verify_err_lines'] == 3 and j['vnz']['verify_err_bytes'] == 10,
             j['vto']['verify_class'] == 'TIMEOUT' and j['vto']['verify_rc'] == 124 and out['vto']['verify_rc'] == 124
             and j['vto']['verify_err_lines'] is None and j['vto']['verify_err_bytes'] is None)
    with Pin():
        dd = {k: C.evaluate(v)['diag']['H4'] for k, v in out.items()}
        # collect сортирует номера процессов как строки ('4242' < '77'); в пробной закрепке TC.TP порядок другой,
        # поэтому для проверки H4 по alt берётся та же закрепка с номерами в порядке collect (как в B11).
        C.PIN_B9 = dict(TEST_PIN, jd_pids=sorted(TEST_PIN['jd_pids']))
        evok = C.evaluate(out['ok'])
    parts += (evok['checks']['H4']['ok'] is True and 'alt=R0V14' in evok['checks']['H4']['value'], dd['rc3']['h4a'] is False, dd['rp']['a_pids'] is False, dd['rr']['a_rx'] is False,
              dd['scan']['h4c_scan_ok'] is False and dd['scan']['h4c_loss_ok'] is True,
              dd['loss']['h4c_loss_ok'] is False and dd['loss']['h4c_scan_ok'] is True,
              dd['rq']['seq_ok'] is False and dd['rq']['alt'] is False,
              dd['vnz']['verify_ok'] is False and dd['vto']['verify_ok'] is False)
    case('R03b_jdiag_from_collect_codes_durations_no_text', all(parts), (parts, j['ok']))
    # R02b — collect B11 и B12 дают одни и те же факты, кроме нового ключа jdiag (тот же вызов, та же подстановка)
    same_c = []
    for kw in ({}, {'rc3': 1}, {'verify': ('rc', 1, b'z\n')}, {'verify': ('timeout', 0, b'')}, {'rp': 1}):
        a, b = fake_collect(MC, **kw), fake_collect(C, **kw)
        same_c.append({k: v for k, v in b.items() if k != 'jdiag'} == a and 'jdiag' not in a)
    case('R02b_collect_b11_b12_same_facts_plus_jdiag', all(same_c), same_c)
    # R04 (чистая часть) — состояния ветки по box и r
    with Pin():
        f = pinned()
        f['verify_rc'] = 1
        f['jdiag'] = fake_collect()['jdiag']
        ev = C.evaluate(f)
        r_fail = {'failed': ev['failed'], 'status': 'BLOCKED_SESSION_UNKNOWN', 'seal': 'BLOCKED_SESSION_UNKNOWN',
                  'reason': 'checks'}
        k1 = kept_box(f)
        _l1, o1 = dl(r_fail, k1)
        fo = pinned()
        _l2, o2 = dl({'failed': [], 'status': 'SAFE_PRE_START', 'seal': 'SEALED_NOW', 'reason': '-'}, kept_box(fo))
        _l3, o3 = dl({'failed': ['COLLECT'], 'status': 'BLOCKED_SESSION_UNKNOWN', 'reason': 'checks'},
                     {'collect_exc': 'OSError'})
        _l4, o4 = dl({'failed': ['COLLECT'], 'status': 'BLOCKED_SESSION_UNKNOWN', 'reason': 'checks'},
                     {'facts': fo, 'facts_sha': R2.facts_sha(fo), 'collect_exc': 'Refused'})
        _l5, o5 = dl({'failed': [], 'status': 'SAFE_PRE_START', 'seal': 'ALREADY_SEALED', 'reason': 'retry'}, {})
        _l6, o6 = dl({'failed': [], 'status': 'BLOCKED_STOP_REVIEW', 'seal': 'REFUSED_INCONSISTENT',
                      'reason': 'obs:x'}, {})
        _l7, o7 = dl({'failed': [], 'status': 'BLOCKED_SESSION_UNKNOWN', 'reason': 'diag_lost_75'}, {})
        bk = kept_box(fo)
        bk['kept'] = (bk['kept'][0], '0' * 64)
        _l8, o8 = dl({'failed': [], 'status': 'SAFE_PRE_START'}, bk)
    parts = (o1['state'] == 'PRIMARY_CHECKS' and o1['failed'] == ['H4'] and o1['ok']['H4'] is False
             and o1['H4']['verify_ok'] is False and o1['H4']['h4a'] is True and o1['jdiag']['verify_class'] == 'OK'
             and o1['origin'] == R2.ORIGIN and o1['obs_sha'] == k1['kept'][1],
             o2['state'] == 'PRIMARY_CHECKS' and all(o2['ok'].values()) and o2['jdiag'] is None,
             o3['state'] == 'COLLECT_ERROR' and o3['code'] == 'OSError' and o3['H4'] is None,
             o4['state'] == 'COLLECT_ERROR' and o4['code'] == 'Refused' and o4['H4'] is None and o4['facts_sha'],
             o5['state'] == o6['state'] == 'RETRY_NOT_EVALUATED' and o5['H4'] is None,
             o7['state'] == 'OTHER' and o7['H4'] is None,
             o8['state'] == 'MISMATCH' and o8['code'] == 'OBS_SHA' and o8['H4'] is None)
    case('R04a_diag_states_by_what_happened', all(parts), parts)
    # R05 (чистая часть) — сбой пересчёта и сериализации → DIAG_ERROR из закрытого списка
    keep = C.evaluate

    def boom(_f):
        raise KeyError('x')
    try:
        C.evaluate = boom
        _l, o = dl({'failed': [], 'status': 'SAFE_PRE_START'}, kept_box(pinned()))
    finally:
        C.evaluate = keep
    keep_o = R2.diag_obj
    try:
        R2.diag_obj = lambda r, box: dict(keep_o(r, box), facts_sha=float('nan'))
        _l2, o2 = dl({'failed': ['H4']}, {})
    finally:
        R2.diag_obj = keep_o
    case('R05a_diag_failures_give_diag_error_closed_code', o == {'v': 1, 'state': 'DIAG_ERROR', 'code': 'KeyError'}
         and o2 == {'v': 1, 'state': 'DIAG_ERROR', 'code': 'ValueError'}, (o, o2))
    # R06 — обезличивание: stderr verify с UUID, путём, номером аренды, 10 КБ, неверным UTF-8 → только числа
    dirty = (f'{TC.LID} /var/lib/zavod/preserve/pb1trial2 {TC.L} 01234567-89ab-cdef-0123-456789abcdef\n'.encode()
             + b'\xff\xfe\x00bad\n' + b'y' * 10240 + b'\n')
    fd = fake_collect(verify=('rc', 1, dirty))
    with Pin():
        ev = C.evaluate(fd)
        line, o = dl({'failed': ev['failed'], 'status': 'BLOCKED_SESSION_UNKNOWN'}, kept_box(fd))
    leaks = [x for x in (TC.LID, TC.L, '/var/', 'preserve', '01234567-89ab', 'yyyy', 'bad') if x in line]
    case('R06_no_lease_id_paths_or_raw_text_in_r2_diag', not leaks and o['state'] == 'PRIMARY_CHECKS'
         and o['jdiag']['verify_err_lines'] == 3 and o['jdiag']['verify_err_bytes'] == len(dirty)
         and not re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-', line), (leaks, o.get('jdiag')))
    # R07 — длинная строка → правильный JSON с error=OVERSIZE, без обрезки
    keep_m = R2.DIAG_MAX
    try:
        R2.DIAG_MAX = 100
        line, o = dl({'failed': []}, kept_box(pinned()))
    finally:
        R2.DIAG_MAX = keep_m
    with Pin():
        full, _o = dl({'failed': []}, kept_box(pinned()))
    case('R07_oversize_is_valid_json_without_truncation', o['error'] == 'OVERSIZE' and o['state'] == 'PRIMARY_CHECKS'
         and o['len'] > 100 and set(o) == {'v', 'state', 'error', 'len'} and len(full) < R2.DIAG_MAX + 8, (o, len(full)))
    # R09 — факты после пересчёта не изменены; изменение поля ВНЕ obs после keep_obs → MISMATCH; не сериализуются
    with Pin():
        f = pinned()
        f['jdiag'] = fake_collect()['jdiag']
        snap = copy.deepcopy(f)
        _l, oa = dl({'failed': []}, kept_box(f))
        unchanged = f == snap
        mism = []
        for mut in (lambda g: g.update(verify_rc=1), lambda g: g.update(journald_active='x'),
                    lambda g: g['jdiag'].update(rc3=5), lambda g: g['scan'].update(n=999)):
            g = copy.deepcopy(f)
            b = kept_box(g)
            mut(g)
            _l, ob = dl({'failed': []}, b)
            mism.append(ob['state'] == 'MISMATCH' and ob['code'] == 'FACTS_SHA' and ob['H4'] is None)
        gu = copy.deepcopy(f)
        gu['odd'] = object()
        bu = kept_box(gu)
        _l, ou = dl({'failed': []}, bu)
    case('R09_facts_unchanged_mutation_mismatch_unhashable', unchanged and oa['state'] == 'PRIMARY_CHECKS'
         and all(mism) and bu['facts_sha'] is None and ou['state'] == 'FACTS_UNHASHABLE' and ou['H4'] is None,
         (unchanged, mism, ou))
    # R10 (чистая часть) — исключение verify (OSError) уходит из collect и в B11, и в B12
    ex = []
    for m in (MC, C):
        try:
            fake_collect(m, verify=('oserror', 0, b''))
            ex.append(None)
        except OSError as e:
            ex.append(type(e).__name__)
    case('R10a_verify_oserror_leaves_collect_in_b11_and_b12', ex == ['OSError', 'OSError'], ex)
    # R11 (чистая часть) — evaluate бросил внутри UN.run_checks при сохранённом файле → EVALUATE_UNKNOWN
    _l, o = dl({'failed': ['COLLECT'], 'status': 'BLOCKED_SESSION_UNKNOWN', 'reason': 'checks'}, kept_box(pinned()))
    case('R11a_evaluate_raised_inside_run_checks_evaluate_unknown', o['state'] == 'COLLECT_ERROR'
         and o['code'] == 'EVALUATE_UNKNOWN' and o['H4'] is None, o)


# ---------------------------------------------------------------------------------------------------------------
def tree_listing(path):
    out = []
    for dp, dn, fn in sorted(os.walk(path)):
        out += [os.path.join(dp, n) for n in sorted(dn + fn)]
    return out


def rooted():
    base = tempfile.mkdtemp(dir='/var/lib')
    os.chmod(base, 0o755)

    def mk(tag):
        P, _f = T2.mk(os.path.join(base, tag))
        os.chmod(P['seal'], 0o700)
        P['obs'] = os.path.join(base, tag, 'r2obs')
        return P

    def main_r2(R, M, Pm, facts, dbm, cm, out=None, ans='SEALED_NOW', argv=None, on_seal=None, collect=None):
        """main() выбранного R2 (B11 или B12) с его модулем проверок M; UN.run_checks видит те же проверки M."""
        keep = (M.collect, M.svc_mask, UN.select_seal, UN.call_seal, UN.C, UN.now_utc)

        def cs(series, _lid, h, *a, **k):
            if on_seal:
                on_seal()
            cm.append(h)
            dbm['row'] = {'series': series, 'proof_sha256': h}
            return ans
        M.collect = collect or (lambda fmt, series, lid, src: facts)
        M.svc_mask = lambda unit: {'svc': facts['svc'], 'mask': facts['mask']}
        UN.select_seal, UN.call_seal, UN.C = (lambda _lid: dbm.get('row')), cs, M
        UN.now_utc = lambda: '2026-11-17T20:00:00Z'               # фиксированные часы: proof B11 и B12 сравнимы
        buf = out if out is not None else io.StringIO()
        try:
            with Pin(), contextlib.redirect_stdout(buf):
                rc = R.main(argv or ['zprobe_r2.py', R.SERIES], Pm)
        finally:
            M.collect, M.svc_mask, UN.select_seal, UN.call_seal, UN.C, UN.now_utc = keep
        lines = buf.getvalue().split('\n') if out is None else []
        DIAGS.extend(x for x in lines if x.startswith('R2_DIAG '))
        return rc, lines

    def diag_of(lines):
        got = [x for x in lines if x.startswith('R2_DIAG ')]
        return json.loads(got[0].split(' ', 1)[1]) if len(got) == 1 else None

    # R01b — proof B11 и B12 на одних фактах побайтно равны, кроме tool_version; строки B11 — те же
    Pa, Pb = mk('p11'), mk('p12')
    rc11, out11 = main_r2(MR, MC, Pa, pinned(), {}, [])
    rc12, out12 = main_r2(R2, C, Pb, pinned(), {}, [])
    ba = open(os.path.join(Pa['seal'], R2.SERIES, '1', 'proof.json'), 'rb').read()
    bb = open(os.path.join(Pb['seal'], R2.SERIES, '1', 'proof.json'), 'rb').read()
    pa, pb = json.loads(ba), json.loads(bb)
    # сумма proof в строке R2 у B11 и B12 разная — proof отличается полем tool_version; сверяется по байтам файла
    ha, hb = hashlib.sha256(ba).hexdigest(), hashlib.sha256(bb).hexdigest()
    tv = (pa.pop('tool_version'), pb.pop('tool_version'))
    sub = (lambda s: s.replace(Pa['obs'], '<obs>').replace(ha, '<sha>'),
           lambda s: s.replace(Pb['obs'], '<obs>').replace(hb, '<sha>'))
    o12 = diag_of(out12)
    case('R01b_proof_and_b11_lines_identical_except_tool_version', rc11 == rc12 == 0 and pa == pb
         and tv == ('zprobe-r2-b11-0.3.checks-0.6', R2.TOOL_VERSION) and len(out11) == 5 and len(out12) == 6
         and ha != hb and ' sha=' + ha + ' ' in out11[0] and ' sha=' + hb + ' ' in out12[0]
         and [sub[0](x) for x in out11[:4]] == [sub[1](x) for x in out12[:4]] and out11[4] == out12[5] == ''
         and o12 and o12['state'] == 'PRIMARY_CHECKS' and all(o12['ok'].values()),
         (rc11, rc12, tv, pa == pb, sorted(k for k in set(pa) | set(pb) if pa.get(k) != pb.get(k)), len(out11), len(out12),
          [i for i in range(4) if sub[0](out11[i]) != sub[1](out12[i])], out11[4:], out12[5:],
          o12 and o12.get('state'), o12 and o12.get('ok'), [x[:120] for x in out12]))
    # R04 (через main) — ранний отказ без R2_DIAG; сбой сбора и сбой keep_obs; повтор; подмена фактов; отказ и успех
    rcu, outu = main_r2(R2, C, mk('u'), pinned(), {}, [], argv=['zprobe_r2.py', 'x'])
    Pi = mk('i')
    os.chmod(os.path.join(Pi['preserve'], R2.SERIES), 0o777)
    rci, outi = main_r2(R2, C, Pi, pinned(), {}, [])

    def raise_os(*a):
        raise OSError(5, 'io')
    rcc, outc = main_r2(R2, C, mk('c'), pinned(), {}, [], collect=raise_os)
    Pk = mk('k')
    loose = os.path.join(base, 'k', 'loose')
    os.mkdir(loose)
    os.chmod(loose, 0o777)
    Pk['obs'] = os.path.join(loose, 'r2obs')
    rck, outk = main_r2(R2, C, Pk, pinned(), {}, [])
    Pr = mk('r')
    dr, cr = {}, []
    main_r2(R2, C, Pr, pinned(), dr, cr)
    rcr, outr = main_r2(R2, C, Pr, pinned(), dr, cr, ans='ALREADY_SEALED')
    fm = pinned()
    rcm, outm = main_r2(R2, C, mk('m'), fm, {}, [], on_seal=lambda: fm['jdiag'].update(rc3=7) if 'jdiag' in fm
                        else fm.update(jdiag={'rc3': 7}))
    ff = pinned()
    ff['verify_rc'] = 1
    rcf, outf = main_r2(R2, C, mk('f'), ff, {}, [])
    ou, oi, oc, ok_, orr, om, of = (diag_of(x) for x in (outu, outi, outc, outk, outr, outm, outf))
    parts = (rcu == 2 and outu == ['usage: zprobe_r2.py pb1trial2', ''],
             rci == 2 and outi[0].startswith('R2=REFUSED_INPUT') and len(outi) == 2 and oi is None,
             rcc == 1 and 'failed=COLLECT' in outc[0] and oc['state'] == 'COLLECT_ERROR' and oc['code'] == 'OSError'
             and oc['H4'] is None,
             rck == 1 and 'failed=COLLECT' in outk[0] and ok_['state'] == 'COLLECT_ERROR' and ok_['code'] == 'Refused'
             and ok_['facts_sha'] is not None,
             rcr == 0 and ' reason=retry' in outr[0] and orr['state'] == 'RETRY_NOT_EVALUATED' and orr['H4'] is None,
             rcm == 0 and om['state'] == 'MISMATCH' and om['code'] == 'FACTS_SHA' and om['H4'] is None,
             rcf == 1 and 'failed=H4 reason=checks' in outf[0] and of['state'] == 'PRIMARY_CHECKS'
             and of['H4']['verify_ok'] is False and of['ok']['H4'] is False and of['failed'] == ['H4'])
    case('R04b_main_states_and_lawful_absence', all(parts), (parts, outi[:2], outk[0][:100]))
    # R05 / R11 (через main) — сбой пересчёта не меняет строку R2=, статус и код; evaluate бросил в run_checks
    calls = [0]
    keep = C.evaluate

    def ev_second_raises(f):
        calls[0] += 1
        if calls[0] >= 2:
            raise TypeError('x')
        return keep(f)
    P5 = mk('e5')
    try:
        C.evaluate = ev_second_raises
        rc5, out5 = main_r2(R2, C, P5, pinned(), {}, [])
    finally:
        C.evaluate = keep
    P5b = mk('e5b')
    rc5b, out5b = main_r2(R2, C, P5b, pinned(), {}, [])

    def ev_raise(f):
        raise RuntimeError('x')
    P11 = mk('e11')
    try:
        C.evaluate = ev_raise
        rc11b, out11b = main_r2(R2, C, P11, pinned(), {}, [])
    finally:
        C.evaluate = keep
    o5, o11 = diag_of(out5), diag_of(out11b)
    case('R05b_recompute_failure_keeps_r2_line_status_code', rc5 == rc5b == 0 and out5[0] == out5b[0]
         and o5 == {'v': 1, 'state': 'DIAG_ERROR', 'code': 'TypeError'}, (rc5, out5[0][:80], o5))
    case('R11b_main_evaluate_raised_in_run_checks', rc11b == 1 and 'failed=COLLECT' in out11b[0]
         and o11['state'] == 'COLLECT_ERROR' and o11['code'] == 'EVALUATE_UNKNOWN', (rc11b, o11))
    # R10 (через main) — OSError verify: B11 и B12 — та же строка R2= и код; B12 R2_DIAG COLLECT_ERROR OSError
    res = []
    for R, M, tag in ((MR, MC, 'v11'), (R2, C, 'v12')):
        fs = FakeSys(verify=('oserror', 0, b''))
        Pv = mk(tag)
        with fs.on(M):
            real = M.collect
            res.append(main_r2(R, M, Pv, pinned(), {}, [], collect=real))
    ov = diag_of(res[1][1])
    case('R10b_verify_oserror_same_line_and_code_b11_b12', res[0][0] == res[1][0] == 1 and res[0][1][0] == res[1][1][0]
         and 'failed=COLLECT' in res[0][1][0] and ov['state'] == 'COLLECT_ERROR' and ov['code'] == 'OSError'
         and ov['H4'] is None and diag_of(res[0][1]) is None, (res[0][1][0][:100], ov))

    # R12 — обрыв stdout на строке R2_DIAG и при сбросе буфера: код запомненный, повторной печати нет, без исключения
    class Broken(io.StringIO):
        def __init__(self, on_diag=True):
            super().__init__()
            self.on_diag = on_diag

        def write(self, s):
            if self.on_diag and 'R2_DIAG' in s:
                raise BrokenPipeError(32, 'stdout closed')
            return super().write(s)

        def flush(self):
            raise BrokenPipeError(32, 'stdout closed')
    got = []
    for tag, on_diag, facts in (('b1', True, pinned()), ('b2', False, pinned()), ('b3', True, dict(pinned(), verify_rc=1))):
        buf = Broken(on_diag)
        try:
            rcb, _ = main_r2(R2, C, mk(tag), facts, {}, [], out=buf)
            got.append((rcb, buf.getvalue().count('R2='), buf.getvalue().count('R2_DIAG'), None))
        except BaseException as e:  # noqa: BLE001
            got.append((None, 0, 0, type(e).__name__))
    case('R12_stdout_broken_on_diag_and_flush_code_kept_no_reprint', got == [(0, 1, 0, None), (0, 1, 1, None),
                                                                            (1, 1, 0, None)], got)
    # R13 — тесты R B11 (без правки) на коде B12: всё PASS, кроме R15 (B12 ловит обрыв stdout — проект 2.2 б)
    code = ("import sys; sys.path.insert(0, %r); import zprobe_r2 as R; R.TOOL = 'zprobe-r2-b11-0.3'; "
            "R.TOOL_VERSION = 'zprobe-r2-b11-0.3.checks-0.6'; import runpy; "
            "runpy.run_path(%r, run_name='__main__')" % (HERE, os.path.join(HERE, 'test_zprobe_r2_b11.py')))
    p = subprocess.run([sys.executable, '-I', '-B', '-c', code], capture_output=True, text=True, timeout=600)
    fails = re.findall(r'^CASE (R\d\d)_\S+ FAIL', p.stdout, re.M)
    passes = re.findall(r'^CASE (R\d\d)_\S+ PASS', p.stdout, re.M)
    case('R13_b11_r_tests_on_b12_only_r15_differs', fails == ['R15'] and len(passes) == 22, (fails, len(passes),
                                                                                             p.stdout[-300:]))


def main():
    pure()
    if ROOT:
        rooted()
    else:
        for n in ('R01b_proof_and_b11_lines_identical_except_tool_version', 'R04b_main_states_and_lawful_absence',
                  'R05b_recompute_failure_keeps_r2_line_status_code', 'R11b_main_evaluate_raised_in_run_checks',
                  'R10b_verify_oserror_same_line_and_code_b11_b12',
                  'R12_stdout_broken_on_diag_and_flush_code_kept_no_reprint', 'R13_b11_r_tests_on_b12_only_r15_differs'):
            skip(n)
    bad = [x for x in DIAGS if not check_schema(x)]
    case('R08_every_complete_r2_diag_line_parses_closed_schema', DIAGS and not bad, (len(DIAGS), bad[:2]))
    print('ZPROBE_R2_B12_TEST=' + ('FAIL' if not OK else 'PASS' if ROOT else 'PASS_NO_ROOT'))
    return 0 if OK else 1


if __name__ == '__main__':
    sys.exit(main())
