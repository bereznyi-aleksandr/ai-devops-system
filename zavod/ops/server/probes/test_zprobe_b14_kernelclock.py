#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_b14_kernelclock.py
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-18 21:45 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-18 21:45 +02:00
# ИСПОЛНИТЕЛЬ: Claude (терминал zavod, пускатель) — B14, замечание аудитора L-355-REL139-01
# НАЗНАЧЕНИЕ: прогон run() и cleanup() бегунка на подставных часах и подставном ядре (не разбор текста программы).
#   Модель ядра повторяет 06_zavod_ext_04.sql и zagent-start: lease_reserve_start (STARTING), lease_mark_running
#   (RUNNING; через 2 минуты — TOO_LATE без смены состояния), lease_start_reconcile (не живая служба: STARTING старше
#   2 минут → START_FAILED, RUNNING → INTERRUPTED), lease_start_overdue (живая STARTING старше 2 минут → остановка и
#   тревога); проход zagent-start — сверка, просроченные, заявки stop, заявки start; таймер — каждую минуту в :00.
#   Случаи: K01 обычный сеанс; K02 длинный сеанс у края бюджета; K03 отметка позже 2 минут (TOO_LATE); K04 отказ базы
#   на отметке; K05 отказ базы после PB1_DONE; K06 сеанс без PB1_DONE; K07 общий предел прогона; K08 — тот же мир на
#   бегунке B13 (путь вторым аргументом) обязан повторить сбой pb1trial3 (остановка ядром, START_FAILED). Ложного
#   RUN_DONE нет ни в одном случае отказа; число вызовов отметки — ровно один.
# ОГРАНИЧЕНИЯ: ничего не запускает и не пишет вне памяти; запуск: python3 -I test_zprobe_b14_kernelclock.py [runner_b13.py]
import importlib.util
import io
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zprobe_rules as R  # noqa: E402
import zprobe_dropin as DROP  # noqa: E402
import zprobe_unstarted as UN  # noqa: E402

OK, BAD = [], []


def case(name, cond, detail=''):
    (OK if cond else BAD).append(name)
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else ' :: ' + str(detail)), flush=True)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LID = '326ef04e-8cc0-4c82-a982-816633fb7a9d'
L = LID.replace('-', '')
UNIT = f'zagent@{L}.service'
S = 'pbsim'


class World:
    """Подставные часы (секунды monotonic) и ядро."""

    def __init__(self, start_delay=3.0, session_len=400.0, db_fail=None, cage_delay=0.0, dropin_delay=0.0):
        self.t = 30.0
        self.start_delay, self.session_len, self.db_fail = start_delay, session_len, db_fail
        self.cage_delay, self.dropin_delay = cage_delay, dropin_delay
        self.session = None
        self.log = []
        self.unit_active, self.pending, self.active_at, self.masked = False, None, None, False
        self.start_req = self.stop_req = False
        self.pb1_done = False
        self.alerts, self.marks, self.passes, self.unknown = [], [], 0, []
        self.store = {}

    # --- часы ---
    def advance(self, dt):
        target = self.t + dt
        while (int(self.t // 60) + 1) * 60 <= target:
            self.t = (int(self.t // 60) + 1) * 60
            self.tick()
            self.kernel_pass()
        self.t = target
        self.tick()

    def tick(self):
        if self.pending is not None and self.t >= self.pending:
            self.pending = None
            if not self.masked and self.session and self.session['status'] == 'STARTING':
                self.unit_active, self.active_at = True, self.t
        if self.unit_active and self.active_at is not None and self.t >= self.active_at + self.session_len:
            self.pb1_done = True

    def stop_unit(self):
        self.unit_active, self.pending = False, None

    # --- ядро ---
    def set_status(self, st):
        self.session['status'] = st
        self.log.append(st)

    def kernel_pass(self):
        self.passes += 1
        live = self.unit_active
        s = self.session
        if s and s['status'] in ('STARTING', 'RUNNING') and not live:          # lease_start_reconcile
            if s['status'] == 'STARTING' and self.t - s['reserved_at'] >= 120:
                self.set_status('START_FAILED')
            elif s['status'] == 'RUNNING':
                self.set_status('INTERRUPTED')                                  # аренда OPEN, не COMPLETED
        if s and live and ((s['status'] == 'STARTING' and self.t - s['reserved_at'] >= 120)
                           or (s['status'] == 'RUNNING' and self.t - s['running_at'] >= 4 * 3600 + 300)):
            self.stop_unit()                                                    # lease_start_overdue
            self.alerts.append(round(self.t - s['reserved_at'], 1))
        if self.stop_req:                                                       # do_stops: аренда OPEN
            self.stop_req = False
            self.stop_unit()
        if self.start_req:                                                      # do_starts
            self.start_req = False
            if self.session is None:
                self.session = {'status': 'STARTING', 'reserved_at': self.t}
                self.log.append('RESERVED')
                if not self.masked:
                    self.pending = self.t + self.start_delay

    def mark_running(self):
        s = self.session
        self.marks.append(None if s is None else round(self.t - s['reserved_at'], 1))
        if s is None or s['status'] != 'STARTING':
            return 'NOT_STARTING'
        if self.t - s['reserved_at'] >= 120:
            return 'TOO_LATE'
        s['running_at'] = self.t
        self.set_status('RUNNING')
        return 'RUNNING'

    def psql(self, q):
        self.advance(0.05)
        if self.db_fail and self.db_fail(self, q):
            return None
        if 'lease_mark_running' in q:
            return self.mark_running()
        if 'INSERT INTO bem_control.chat_lease' in q:
            return ''
        if 'FROM bem_control.session_start WHERE' in q:
            return self.session['status'] if self.session else 'NONE'
        if 'FROM bem_control.chat_lease WHERE lease_id' in q:
            return 'OPEN'
        if 'holder_session' in q:
            return LID
        self.unknown.append(('psql', q[:80]))
        return ''


def install(M, W):
    """Подменить внешний мир бегунка M миром W. Возвращает функцию возврата общих модулей."""
    def sh(*args, timeout=30, check=True, inp=None):
        a = list(args)
        if a[:3] == ['runuser', '-u', 'postgres']:
            out = W.psql(inp)
            if out is None:
                if check:
                    raise M.Abort('runuser_rc_1')
                return ''
            return out + '\n'
        if a[:3] == ['runuser', '-u', 'zkernel'] and a[4] == 'touch':
            if a[5] == f'/run/zavod/start/{L}':
                W.start_req = True
            elif a[5] == f'/run/zavod/stop/{L}':
                W.stop_req = True
            else:
                W.unknown.append(a)
            return ''
        if a[0] == 'systemctl':
            if a[1:3] == ['start', 'zagent-start.service']:
                W.kernel_pass()
                W.advance(1.0)
                return ''
            if a[1] == 'is-active':
                return ('active' if a[2] == UNIT and W.unit_active else 'inactive') + '\n'
            if a[1] == 'daemon-reload':
                return ''
            if a[1] == '--version':
                return 'systemd 255 (255.4-1ubuntu8.11)\n'
            if a[1] == 'stop' and a[2] == UNIT:
                W.stop_unit()
                W.advance(1.0)
                return ''
            if a[1:4] == ['mask', '--runtime', UNIT]:
                W.masked = True
                return ''
        if a == ['cat', '/proc/sys/kernel/random/uuid']:
            return LID + '\n'
        if a[0] == 'ip':
            return ''
        if a[0] == 'nft':
            return 'table inet zavod {\n}\n'
        if a[:2] == ['id', '-u']:
            return '998\n'
        if a[:2] == ['id', '-g']:
            return '997\n'
        if a[0] == 'git':
            return 'git version 2.43.0\n'
        W.unknown.append(a)
        return ''

    def show(unit, *props):
        if not props:
            W.advance(W.dropin_delay / 2)
            return {'ExecStart': 'x', 'Environment': ''}
        if props == ('ExecStart', 'DropInPaths'):
            return {'ExecStart': 'x', 'DropInPaths': ''}
        if props == ('LoadState',):
            return {'LoadState': 'masked' if W.masked else 'loaded'}
        W.advance(W.cage_delay)
        return {'InvocationID': 'a' * 32, 'MainPID': '4242', 'ControlGroup': f'/zagent.slice/{UNIT}',
                'IPAddressDeny': 'any', 'IPAddressAllow': '', 'InaccessiblePaths': '-/nonexistent-zprobe-sim'}

    def journal(*filters, since):
        W.advance(0.2)
        if filters and filters[0].startswith('_SYSTEMD_INVOCATION_ID=') and W.pb1_done:
            return [{'_SYSTEMD_UNIT': UNIT, '_PID': '4242', '_UID': '61200', 'MESSAGE': 'PB1_DONE',
                     '__REALTIME_TIMESTAMP': '1795000000000000'}]
        return []

    def fopen(path, mode='r', encoding=None, **kw):
        p = str(path).replace('\\', '/')
        if p in W.store:
            return io.StringIO(W.store[p])
        if p.endswith('/request.json'):
            return io.StringIO(json.dumps({'series': S, 'probes': R.PROBES, 'challenge': 'c' * 32}))
        if p.endswith('/RELEASE'):
            return io.StringIO('commit=' + '0' * 40 + '\nversion=3.5.5-b14\n')
        if p == '/proc/sys/kernel/random/boot_id':
            return io.StringIO('b' * 8 + '-' + 'b' * 4 + '-' + 'b' * 4 + '-' + 'b' * 4 + '-' + 'b' * 12 + '\n')
        if p == '/proc/4242/status':
            return io.StringIO('Name:\tpython3\nUid:\t61200\t61200\t61200\t61200\n')
        if p == '/proc/4242/cgroup':
            return io.StringIO(f'0::/zagent.slice/{UNIT}\n')
        if p == '/proc/4242/mountinfo':
            return io.StringIO('')
        raise FileNotFoundError(p)

    def put_new(path, data, mode, gid=0):
        p = str(path).replace('\\', '/')
        if p in W.store:
            raise M.Abort('exists_' + os.path.basename(p))
        W.store[p] = data

    class OsProxy:
        path = os.path

        def __getattr__(self, k):
            return getattr(os, k)

        @staticmethod
        def stat(p):
            return types.SimpleNamespace(st_ino=7)

        @staticmethod
        def uname():
            return types.SimpleNamespace(release='6.8.0-sim')

        @staticmethod
        def close(fd):
            return None

    class TimeProxy:
        @staticmethod
        def monotonic():
            return W.t

        @staticmethod
        def time():
            return 1795000000 + W.t

        @staticmethod
        def sleep(s):
            W.advance(s)

    def snapshot():
        W.advance(2.0)
        return [f'140.82.112.{i}' for i in range(1, 14)], {}, 'f' * 64

    def tcp_ok(ip, port):
        W.advance(0.01)
        return False

    dec = {'doc': {'result': 'OK', 'changed': [], 'raw_changed': [], 'extra': []}, 'code': 'OK', 'diag_status': 'OK',
           'logged': True, 'exit_code': 0, 'proceed': True, 'abort': None}

    def dropin_verdict(*a):
        W.advance(W.dropin_delay / 2)
        return dict(dec), {'props_ok': True}

    for k, v in dict(sh=sh, show=show, journal=journal, open=fopen, put_new=put_new, os=OsProxy(), time=TimeProxy,
                     snapshot_targets=snapshot, tcp_ok=tcp_ok, proxy_probe_from_host=lambda: (40000, 403),
                     mkdirs_sync=lambda p, m: None, dropin_verdict=dropin_verdict, code_fingerprints=lambda sha=None: {},
                     keep_copy=lambda series, path: 'kept', unstarted_deps=lambda series, st: None).items():
        setattr(M, k, v)
    saved = [(UN, 'series_taken'), (UN, 'take_anchor'), (UN, 'open_src'), (UN, 'write_anchor'),
             (UN, 'seal_unstarted'), (DROP, 'emit'), (R, 'collect_session')]
    old = [(m, n, getattr(m, n)) for m, n in saved]
    UN.series_taken = lambda series, places: False
    UN.take_anchor = lambda *a: {}
    UN.open_src = lambda d: 99
    UN.write_anchor = lambda fd, doc: 'a' * 64
    UN.seal_unstarted = lambda *a: {'status': 'SAFE_PRE_START'}
    DROP.emit = lambda line: True
    R.collect_session = lambda lines: ([], None)

    def restore():
        for m, n, v in old:
            setattr(m, n, v)
    return restore


def simulate(path, name, **kw):
    """Один прогон: run() как в main(), затем ExecStopPost cleanup(). Итог — словарь фактов."""
    W = World(**kw)
    M = load(path, name)
    restore = install(M, W)
    try:
        if hasattr(M, 'T0'):
            M.T0[0] = W.t
        t0 = W.t
        ev = {'series': S, 'status': 'RUNNING'}
        try:
            M.run(S, ev)
        except Exception as e:  # noqa: BLE001 — как main()
            ev.update(status='ABORTED', reason=type(e).__name__ + ':' + str(e)[:200])
        t_run = W.t - t0
        log_before_cleanup = list(W.log)
        t1 = W.t
        try:
            rc = M.cleanup(S)
            cl = json.loads(W.store.get(f'/run/zprobe/{S}/cleanup.json', W.store.get(
                os.path.join('/run/zprobe', S, 'cleanup.json').replace('\\', '/'), '{}')))
        except Exception as e:  # noqa: BLE001 — ExecStopPost=-: сбой уборки не валит службу, но cleanup.json нет
            rc, cl = 'exception', {'status': 'EXCEPTION:' + type(e).__name__ + ':' + str(e)[:80]}
        return {'ev': ev, 't_run': round(t_run, 1), 't_cleanup': round(W.t - t1, 1), 'rc': rc, 'cl': cl,
                'log': W.log, 'log_run': log_before_cleanup, 'alerts': W.alerts, 'marks': W.marks,
                'passes': W.passes, 'unknown': W.unknown, 'M': M}
    finally:
        restore()


B14 = os.path.join(HERE, 'zprobe_runner.py')
SEALED = set(R.SEALED)

# K01 обычный сеанс 400 с (больше прежнего окна 300 с B13)
x = simulate(B14, 'runner_k01', session_len=400.0)
case('K01a normal: RUN_DONE', x['ev']['status'] == 'RUN_DONE', x['ev'])
case('K01b mark_running exactly once, within 2 min of reservation',
     len(x['marks']) == 1 and x['marks'][0] is not None and x['marks'][0] < 120, x['marks'])
case('K01c kernel never stopped the session (no overdue alert)', x['alerts'] == [], x['alerts'])
case('K01d kernel log RESERVED, RUNNING, INTERRUPTED; run saw a sealed state',
     x['log'] == ['RESERVED', 'RUNNING', 'INTERRUPTED'] and x['ev'].get('lease_state') == 'INTERRUPTED', (x['log'], x['ev']))
case('K01e cleanup SAFE (state sealed), rc 0', x['cl'].get('status') == 'SAFE' and x['rc'] == 0, x['cl'])
case('K01f run within TimeoutStartSec', x['t_run'] < x['M'].RUN_TIMEOUT, x['t_run'])
case('K01g no unknown command or query', x['unknown'] == [], x['unknown'])

# K02 длинный сеанс у края бюджета (13 адресов, 8 имён → 831 с)
x = simulate(B14, 'runner_k02', session_len=800.0)
case('K02 long session 800 s: RUN_DONE, no overdue, one mark', x['ev']['status'] == 'RUN_DONE' and x['alerts'] == []
     and len(x['marks']) == 1 and x['cl'].get('status') == 'SAFE', (x['ev'].get('reason'), x['alerts'], x['cl']))

# K03 проверка клетки затянулась: отметка позже 2 минут брони
x = simulate(B14, 'runner_k03', cage_delay=125.0)
case('K03a late mark: ABORTED at mark_running, no PASS',
     x['ev']['status'] == 'ABORTED' and x['ev'].get('step') == 'mark_running'
     and 'mark_running_' in x['ev'].get('reason', ''), x['ev'])
case('K03b late mark: answer TOO_LATE or NOT_STARTING, never RUNNING',
     'RUNNING' not in x['log'] and len(x['marks']) == 1 and x['marks'][0] >= 120, (x['log'], x['marks']))
case('K03c late mark: no PB1 collect, cleanup SAFE with START_FAILED',
     'attempts' not in x['ev'] and x['cl'].get('status') == 'SAFE' and x['cl'].get('session_state') == 'START_FAILED',
     x['cl'])

# K04 отказ базы на отметке (через 10 с после брони)
x = simulate(B14, 'runner_k04', db_fail=lambda w, q: 'lease_mark_running' in q)
case('K04a db error at mark: ABORTED runuser_rc_1 at mark_running',
     x['ev']['status'] == 'ABORTED' and x['ev'].get('step') == 'mark_running' and 'runuser_rc_1' in x['ev']['reason'],
     x['ev'])
case('K04b db error at mark: cleanup waits for the kernel (STARTING -> START_FAILED), SAFE within 600 s',
     x['cl'].get('status') == 'SAFE' and x['cl'].get('session_state') == 'START_FAILED' and x['t_cleanup'] < 600,
     (x['cl'], x['t_cleanup']))

# K05 отказ базы после PB1_DONE (чтение состояния сеанса)
x = simulate(B14, 'runner_k05', db_fail=lambda w, q: w.pb1_done and 'FROM bem_control.session_start' in q)
case('K05 db error after PB1_DONE: ABORTED in stop, no RUN_DONE, cleanup not SAFE',
     x['ev']['status'] == 'ABORTED' and x['ev'].get('step') == 'stop' and x['cl'].get('status') != 'SAFE',
     (x['ev'], x['cl']))

# K06 сеанс без PB1_DONE: окно по бюджету, отказ session_not_done
x = simulate(B14, 'runner_k06', session_len=10 ** 6)
case('K06 no PB1_DONE: ABORTED session_not_done after the budget, before TimeoutStartSec, cleanup SAFE INTERRUPTED',
     x['ev']['status'] == 'ABORTED' and x['ev'].get('reason', '').endswith('session_not_done')
     and x['ev'].get('collect_room_s') == x['ev'].get('collect_budget_s') and x['t_run'] < x['M'].RUN_TIMEOUT
     and x['alerts'] == [] and x['cl'].get('status') == 'SAFE' and x['cl'].get('session_state') == 'INTERRUPTED',
     (x['ev'].get('reason'), x['t_run'], x['cl']))

# K07 долгие шаги до старта: окно collect сжато общим пределом прогона
x = simulate(B14, 'runner_k07', session_len=10 ** 6, dropin_delay=1400.0)
M7 = x['M']
case('K07 run deadline clamps collect window; run ends before RUN_TIMEOUT - RUN_RESERVE + stop margin',
     x['ev']['status'] == 'ABORTED' and x['ev'].get('collect_room_s', 10 ** 9) < x['ev'].get('collect_budget_s', 0)
     and x['t_run'] < M7.RUN_TIMEOUT - M7.RUN_RESERVE + 120 and x['cl'].get('status') == 'SAFE',
     (x['ev'].get('collect_room_s'), x['ev'].get('collect_budget_s'), x['t_run'], x['cl']))

# K08 тот же мир на бегунке B13 — сбой pb1trial3 повторяется (контроль модели)
if len(sys.argv) > 1:
    x = simulate(sys.argv[1], 'runner_b13', session_len=400.0)
    case('K08a B13 runner: kernel stops STARTING session after 2 min (overdue alert)',
         len(x['alerts']) == 1 and 120 <= x['alerts'][0] < 181, x['alerts'])
    case('K08b B13 runner: ABORTED session_not_done, no RUNNING, START_FAILED (as pb1trial3)',
         x['ev']['status'] == 'ABORTED' and x['ev'].get('reason', '').endswith('session_not_done')
         and 'RUNNING' not in x['log_run'] and 'START_FAILED' in x['log'], (x['ev'].get('reason'), x['log']))
else:
    print('SKIP K08 (path of the B13 runner not given)')

# Служба B14: TimeoutStartSec равен RUN_TIMEOUT бегунка; запас уборки не меньше ожидания сверки
unit = os.path.join(HERE, 'zprobe-run-b14@.service')
if os.path.exists(unit):
    txt = open(unit, encoding='utf-8').read()
    M = load(B14, 'runner_unit')
    case('K09 unit zprobe-run-b14@: TimeoutStartSec = RUN_TIMEOUT',
         f'\nTimeoutStartSec={M.RUN_TIMEOUT}\n' in txt, M.RUN_TIMEOUT)
    case('K10 unit TimeoutStopSec covers stop 120 s + settle 30 x 6 s',
         any(ln.startswith('TimeoutStopSec=') and int(ln.split('=')[1]) >= 120 + M.SETTLE_TRIES * 6 + 60
             for ln in txt.splitlines()), [ln for ln in txt.splitlines() if 'TimeoutStopSec' in ln])
else:
    case('K09 unit zprobe-run-b14@.service present', False, unit)

print(f'ZPROBE_B14_KERNELCLOCK_TESTS {len(OK)}/{len(OK) + len(BAD)} {"PASS" if not BAD else "FAIL"}')
sys.exit(1 if BAD else 0)
