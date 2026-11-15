#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_unstarted.py
# ВЕРСИЯ: v0.2 (выпуск B10)  СТАТУС: DRAFT
# v0.2 (2026-11-15, терминал zavod, чат cb6b67c5): факты прохода H5 несут first_cursor (REL65 M-03).
# ДАТА СОЗДАНИЯ: 2026-11-14 23:42 +02:00  ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · напарник · 04» (869221b9)
# НАЗНАЧЕНИЕ: проверки zprobe_unstarted.py (проект B10 v0.18 1.3 H2-B10/H9 б и 4.1): строки журнала, занятые имена,
#   якорь бегунка (ограниченное чтение журнала, закрытый состав, запись O_EXCL), эталон файла службы, итог уборки.
#   U01–U22 — без системы (везде); U23–U32 — Linux от root (в CI под sudo), иначе SKIP. Итог ZPROBE_UNSTARTED_TEST.
import copy
import hashlib
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zprobe_checks as C  # noqa: E402
import zprobe_seal as Z  # noqa: E402
import zprobe_unstarted as U  # noqa: E402

OK, SKIPPED = True, 0
LID = '0123abcd-0000-4000-8000-00000000c0de'
L = LID.replace('-', '')
S = 'b10s1'
BOOT = 'bc77431f' + '0' * 24
T0 = 1_794_600_000
CUR = f's={"a" * 32};i=1f;b={BOOT};m=2a;t=5f1;x=9'
SHA = 'f' * 64
PY = sys.executable


def case(name, cond):
    global OK
    OK &= bool(cond)
    print('CASE', name, 'PASS' if cond else 'FAIL', flush=True)


def refused(fn, *a, want=None, **kw):
    try:
        fn(*a, **kw)
    except Z.Refused as e:
        return want is None or want in str(e)
    return False


def facts():
    """Эталонные факты B10 (как test_zprobe_checks.py facts('b10')): все H1–H10 проходят."""
    st = {'series': S, 'runner': 'b10', 'lease': L, 'lease_id': LID,
          'dropin': f'/run/systemd/system/zagent@{L}.service.d/50-zprobe.conf'}
    return {'fmt': 'b10', 'series': S, 'lid': LID, 'boot_now': BOOT, 'btime': T0 - 3600,
            'lease_row': {'lease_id': LID, 'status': 'OPEN', 'holder_session': 'zprobe-' + S, 'opened_by': 'zprobe-run',
                          'role_key': '01_install_probe', 'opened_at_s': T0},
            'state': st, 'state_sha_run': SHA, 'state_sha_manifest': None, 'evidence_lease': L,
            'evidence_since_s': None,
            'anchor': {'series': S, 'lease': L, 'lease_id': LID, 'boot_id': BOOT, 'cursor': CUR,
                       'cursor_us': (T0 + 1) * 1000000, 'utc': '2026-11-14T21:40:01Z'},
            'anchor_cursor_ok': True,
            'unit_entries': {'start_jobs': [T0 - 10], 'lease_open': [T0 - 1], 'boots': [BOOT]},
            'other_runner_count': 0,
            'fragment': {'path': U.TEMPLATE, 'sha': SHA, 'safe': True},
            'fragment_expected': {'path': U.TEMPLATE, 'sha': SHA},
            'first_entry_s': T0 - 3600 + 2, 'journald_active': 'active', 'journald_mono_us': 3_000_000, 'verify_rc': 0,
            'scan': {'rc': 0, 'n': 120, 'unit_hits': 0, 'start_hits': 0, 'loss': 0, 'other': 0, 'first_cursor': CUR,
                     'last_cursor': CUR},
            'db': {'session_start': 0, 'session_start_log': 0, 'gate_command': 0, 'live': 0}, 'named_files': 0,
            'svc': {'ActiveState': 'inactive', 'InvocationID': '', 'ActiveEnterTimestamp': ''},
            'mask': {'link': '/dev/null', 'LoadState': 'masked', 'UnitFileState': 'masked-runtime', 'etc_exists': False},
            'first_start_request_s': None}


def entry_cmd(code):
    return (PY, '-I', '-c', code)


# ---- строки журнала и имена ----
lo = U.lease_open_line(S, LID)
case('U01 lease open line = the line evaluate counts for H2-B10',
     lo == f'ZPROBE_LEASE_OPEN series={S} lease_id={LID}' and U.anchor_line(S, LID) != lo)
tmp = tempfile.mkdtemp(prefix='zunst-')
os.mkdir(os.path.join(tmp, 'old'))
case('U02 series_taken: pb1trial2 always, existing name in a place, free name -> None',
     U.series_taken('pb1trial2', [tmp]) == 'b9_residue' and U.series_taken('old', ['/nonexistent-x', tmp]) == tmp
     and U.series_taken('fresh', [tmp]) is None)

# ---- якорь: ожидание записи не раньше конца INSERT ----
seq = [{'cursor': CUR, 'us': (T0 - 2) * 1000000, 'boot': BOOT}, {'cursor': CUR, 'us': (T0 + 1) * 1000000, 'boot': BOOT}]
emitted, slept = [], []
doc = U.take_anchor(S, LID, T0, BOOT, lambda: '2026-11-14T21:40:01Z', entry=lambda: seq.pop(0),
                    emit=lambda ln: emitted.append(ln) or True, sleep=slept.append)
case('U03 take_anchor waits for an entry >= after_s, emits the anchor line once',
     doc == {'series': S, 'lease': L, 'lease_id': LID, 'boot_id': BOOT, 'cursor': CUR, 'cursor_us': (T0 + 1) * 1000000,
             'utc': '2026-11-14T21:40:01Z'} and emitted == [U.anchor_line(S, LID)] and slept == [0.5]
     and U.check_anchor(doc))
slept = []
case('U04 take_anchor: entries of another boot only -> anchor_no_entry after all tries',
     refused(U.take_anchor, S, LID, T0, BOOT, U.now_utc, want='anchor_no_entry',
             entry=lambda: {'cursor': CUR, 'us': (T0 + 5) * 1000000, 'boot': 'e' * 32}, emit=lambda ln: True,
             sleep=slept.append, tries=4) and slept == [0.5, 0.5, 0.5])
calls = []
case('U05 take_anchor: anchor line not written -> anchor_emit, journal not read',
     refused(U.take_anchor, S, LID, T0, BOOT, U.now_utc, want='anchor_emit', entry=lambda: calls.append(1),
             emit=lambda ln: False) and calls == [])
bad = []
for k, v in (('extra', 1), ('cursor', 'nocursor'), ('cursor_us', '5'), ('boot_id', 'e' * 32), ('utc', 'now'),
             ('lease', 'e' * 32)):
    d = dict(doc)
    d[k] = v
    bad.append(not U.check_anchor(d))
d = dict(doc)
del d['utc']
bad.append(not U.check_anchor(d))
case('U06 check_anchor: extra/missing field, bad cursor or time, cursor b= != boot_id, lease != lease_id', all(bad))

# ---- ограниченное чтение последней записи (подставной journalctl) ----
good_line = json.dumps({'__CURSOR': CUR, '__REALTIME_TIMESTAMP': str((T0 + 3) * 1000000), '_BOOT_ID': BOOT})
e = U.last_entry(entry_cmd(f'print({good_line!r})'))
case('U07 last_entry: one JSON line -> cursor, time in us, boot', e == {'cursor': CUR, 'us': (T0 + 3) * 1000000,
                                                                         'boot': BOOT})
case('U08 last_entry: journalctl exits 3 without output -> journalctl_rc_3',
     refused(U.last_entry, entry_cmd('import sys; sys.exit(3)'), want='journalctl_rc_3'))
case('U09 last_entry: line longer than the limit -> too_big_out',
     refused(U.last_entry, entry_cmd("print('x' * 5000)"), limit=1000, want='too_big_out'))
case('U10 last_entry: hangs without output -> anchor_timeout (process killed)',
     refused(U.last_entry, entry_cmd('import time; time.sleep(30)'), timeout=1, want='anchor_timeout'))
case('U11 last_entry: entry without __CURSOR -> no_cursor',
     refused(U.last_entry, entry_cmd("print('{\"_BOOT_ID\": \"%s\"}')" % BOOT), want='no_cursor'))
case('U12 last_entry: cursor of wrong form -> bad_cursor',
     refused(U.last_entry, entry_cmd('print(%r)' % json.dumps({'__CURSOR': 'abc', '__REALTIME_TIMESTAMP': '5',
                                                                '_BOOT_ID': BOOT})), want='bad_cursor'))
case('U13 last_entry: output without final newline -> no_cursor',
     refused(U.last_entry, entry_cmd(f'import sys; sys.stdout.write({good_line!r})'), want='no_cursor'))

# ---- итог уборки (общий порядок печати подменён, чтобы проверить решение после печати без системы) ----
real_seal = Z.seal


class DB:
    def __init__(self, row=None, fail=False):
        self.row, self.fail, self.n = row, fail, 0

    def select(self, lid):
        self.n += 1
        if self.fail:
            raise RuntimeError('psql_rc_2')
        return self.row


def deps(db, collect=facts, recheck=None, exit_status=None):
    rc = recheck or (lambda: {'svc': facts()['svc'], 'mask': facts()['mask']})
    return {'exit_status': exit_status, 'collect': collect, 'recheck_facts': rc, 'select_row': db.select,
            'call_seal': lambda s, lid, sha: 'SEALED_NOW', 'open_source': None, 'tool_version': 'b10-test',
            'now_utc': lambda: '2026-11-14T21:41:00Z'}


def fake_seal(result, sha=SHA, run=True, boom=False):
    def f(kind, series, lid, select_row, call, run_checks, recheck, open_source, tool, now, **kw):
        if boom:
            raise RuntimeError('connection lost')
        if run:
            ev = run_checks()
            if not ev['ok']:
                return {'result': 'BLOCKED_SESSION_UNKNOWN', 'reason': 'checks'}
        return {'result': result, 'k': 1, 'sha': sha, 'reason': 'first'}
    return f


def go(result, db, **kw):
    Z.seal = fake_seal(result, **{k: kw.pop(k) for k in ('sha', 'run', 'boom') if k in kw})
    try:
        return U.seal_unstarted(S, LID, deps(db, **kw))
    finally:
        Z.seal = real_seal


row = {'series': S, 'proof_sha256': SHA}
r = go('SEALED_NOW', DB(row))
case('U14 SEALED_NOW, row = proof sum, H8/H10 again ok -> SAFE_PRE_START', r['status'] == 'SAFE_PRE_START'
     and r['seal'] == 'SEALED_NOW' and r['failed'] == [])
case('U15 ALREADY_SEALED (retry branch) -> SAFE_PRE_START', go('ALREADY_SEALED', DB(row))['status'] == 'SAFE_PRE_START')
state = {'n': 0}


def mask_goes():
    state['n'] += 1
    f = facts()
    return {'svc': f['svc'], 'mask': dict(f['mask'], link=None)}


case('U16 mask gone after the seal -> BLOCKED_STOP_REVIEW (seal stays)',
     go('SEALED_NOW', DB(row), recheck=mask_goes)['status'] == 'BLOCKED_STOP_REVIEW')
case('U17 seal row with another sum after the call -> BLOCKED_STOP_REVIEW',
     go('SEALED_NOW', DB(dict(row, proof_sha256='e' * 64)))['status'] == 'BLOCKED_STOP_REVIEW')
r = go('REFUSED_INCONSISTENT', DB(row))
case('U18 REFUSED_INCONSISTENT -> BLOCKED_STOP_REVIEW (4.4 p.2)', r['status'] == 'BLOCKED_STOP_REVIEW')
outs = [go(x, DB(row))['status'] for x in ('REFUSED_HAS_SESSION', 'REFUSED_NOT_OWN', 'BLOCKED_SESSION_UNKNOWN')]
case('U19 any other answer -> BLOCKED_SESSION_UNKNOWN', outs == ['BLOCKED_SESSION_UNKNOWN'] * 3)


def broken():
    f = facts()
    f['scan'] = dict(f['scan'], other=1)
    return f


r = go('SEALED_NOW', DB(None), collect=broken)
case('U20 H5 fails -> BLOCKED_SESSION_UNKNOWN, failed = [H5]', r['status'] == 'BLOCKED_SESSION_UNKNOWN'
     and r['failed'] == ['H5'])
r = go('SEALED_NOW', DB(None), collect=lambda: (_ for _ in ()).throw(RuntimeError('psql_rc_2')))
case('U21 fact collection fails -> BLOCKED_SESSION_UNKNOWN, failed = [COLLECT]',
     r['status'] == 'BLOCKED_SESSION_UNKNOWN' and r['failed'] == ['COLLECT'])
db = DB(row)
r1 = go('SEALED_NOW', db, exit_status='75')
r2 = go('SEALED_NOW', DB(row), boom=True)
case('U22 exit 75 -> BLOCKED diag_lost_75 without seal; call outcome unknown -> BLOCKED seal_exc',
     r1['status'] == 'BLOCKED_SESSION_UNKNOWN' and r1['reason'] == 'diag_lost_75' and r1['seal'] is None
     and db.n == 0 and r2['status'] == 'BLOCKED_SESSION_UNKNOWN' and r2['reason'].startswith('seal_exc'))

# ---- папки, файлы и полный порядок печати — Linux от root ----
FS = os.name == 'posix' and hasattr(os, 'geteuid') and os.geteuid() == 0
FS_CASES = ['U23 open_src: root dir with group zprobe 0750 accepted (gid not 0)',
            'U24 open_src: group-writable step -> src_dir_owner', 'U25 open_src: symlink step -> OSError',
            'U26 write_anchor: canon bytes, root 0600, sum returned, second write refused',
            'U27 write_anchor: bad schema -> anchor_schema, no file',
            'U28 expected_fragment: one line -> path+sum; dup, mode 0666, no final newline, absent -> None',
            'U29 seal_unstarted with real seal order: SAFE_PRE_START, k=1, proof sum = row, cleanup.json not in src',
            'U30 second cleanup after the seal (retry branch): SAFE_PRE_START, ALREADY_SEALED, no k=2',
            'U31 H8 fails: BLOCKED_SESSION_UNKNOWN, no attempt folder, no SQL call',
            'U32 mask gone after the seal call: BLOCKED_STOP_REVIEW, proof and row stay']
if not FS:
    for n in FS_CASES:
        print('CASE', n.split(' ', 1)[0], n.split(' ', 1)[1], 'SKIP (needs Linux root)', flush=True)
        SKIPPED += 1
else:
    base = tempfile.mkdtemp(prefix='zunst-test-', dir='/var/lib')
    os.chmod(base, 0o755)
    run = os.path.join(base, 'run')
    os.mkdir(run, 0o750)
    os.chown(run, 0, 65534)
    fd = U.open_src(run)
    case(FS_CASES[0], isinstance(fd, int))
    os.close(fd)
    gw = os.path.join(base, 'gw')
    os.mkdir(gw)
    os.chmod(gw, 0o770)
    os.mkdir(os.path.join(gw, 'in'))
    case(FS_CASES[1], refused(U.open_src, os.path.join(gw, 'in'), want='src_dir_owner'))
    os.symlink(run, os.path.join(base, 'lnk'))
    try:
        U.open_src(os.path.join(base, 'lnk'))
        followed = True
    except OSError:
        followed = False
    case(FS_CASES[2], not followed)

    ser = os.path.join(run, S)
    os.mkdir(ser, 0o750)
    os.chown(ser, 0, 65534)
    sfd = U.open_src(ser)
    h = U.write_anchor(sfd, doc)
    st = os.stat(U.ANCHOR, dir_fd=sfd)
    try:
        U.write_anchor(sfd, doc)
        second = True
    except FileExistsError:
        second = False
    case(FS_CASES[3], h == hashlib.sha256(Z.canon(doc)).hexdigest() and st.st_mode & 0o777 == 0o600
         and st.st_uid == 0 and not second)
    os.mkdir(os.path.join(base, 'a2'), 0o700)
    a2 = U.open_src(os.path.join(base, 'a2'))
    case(FS_CASES[4], refused(U.write_anchor, a2, dict(doc, extra=1), want='anchor_schema')
         and os.listdir(a2) == [])

    def lst(name, text, mode=0o644):
        p = os.path.join(base, name)
        with open(p, 'w', encoding='ascii') as f:
            f.write(text)
        os.chmod(p, mode)
        return p
    line = f'{SHA}  {U.TEMPLATE}\n'
    other = f'{"1" * 64}  /etc/systemd/system/zprobe-journal-b10@.service\n'
    case(FS_CASES[5], U.expected_fragment(lst('i1', other + line)) == {'path': U.TEMPLATE, 'sha': SHA}
         and U.expected_fragment(lst('i2', line + line)) is None
         and U.expected_fragment(lst('i3', line, 0o666)) is None
         and U.expected_fragment(lst('i4', line.rstrip('\n'))) is None
         and U.expected_fragment(os.path.join(base, 'absent')) is None)

    # источник серии: файлы бегунка (root:zprobe 0640) + anchor_run.json (уже записан) + cleanup.json (исключение)
    for n in ('request.json', 'state.json', 'dropin_check.json', 'evidence.json', 'cleanup.json'):
        f = os.open(n, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o640, dir_fd=sfd)
        os.write(f, ('{"n":"%s"}' % n).encode())
        os.fchown(f, 0, 65534)
        os.fchmod(f, 0o640)
        os.close(f)
    os.close(sfd)
    os.mkdir(os.path.join(base, 'seal'), 0o755)
    SEAL = os.path.join(base, 'seal')

    class RDB:
        def __init__(self):
            self.row, self.calls = None, []

        def select(self, lid):
            return self.row

        def call(self, s, lid, sha):
            self.calls.append(sha)
            if self.row is None:
                self.row = {'series': s, 'proof_sha256': sha}
                return 'SEALED_NOW'
            return 'ALREADY_SEALED' if self.row['proof_sha256'] == sha else 'REFUSED_INCONSISTENT'

    def opener(path):
        def f():
            fd = U.open_src(path)
            return fd, path, {n: (None, None) for n in Z.matrix('cleanup', Z.src_names(fd))}
        return f

    def real_deps(db, series=S, collect=facts, recheck=None):
        return {'exit_status': None, 'collect': collect,
                'recheck_facts': recheck or (lambda: {'svc': facts()['svc'], 'mask': facts()['mask']}),
                'select_row': db.select, 'call_seal': db.call, 'open_source': opener(os.path.join(run, series)),
                'tool_version': 'b10-test', 'now_utc': lambda: '2026-11-14T21:41:00Z', 'root': SEAL}

    rdb = RDB()
    r = U.seal_unstarted(S, LID, real_deps(rdb))
    pj = os.path.join(SEAL, S, '1', 'proof.json')
    srcs = sorted(os.listdir(os.path.join(SEAL, S, '1', 'src'))) if os.path.isdir(os.path.join(SEAL, S, '1')) else []
    with open(pj, 'rb') as f:
        psha = hashlib.sha256(f.read()).hexdigest()
    case(FS_CASES[6], r['status'] == 'SAFE_PRE_START' and r['seal'] == 'SEALED_NOW' and r['k'] == 1
         and rdb.row['proof_sha256'] == psha == r['sha'] and 'cleanup.json' not in srcs and U.ANCHOR in srcs
         and 'INVENTORY.sha256' in srcs)
    r = U.seal_unstarted(S, LID, real_deps(rdb))
    case(FS_CASES[7], r['status'] == 'SAFE_PRE_START' and r['seal'] == 'ALREADY_SEALED'
         and sorted(os.listdir(os.path.join(SEAL, S))) == ['1'])

    s2 = 'b10s2'
    os.mkdir(os.path.join(run, s2), 0o750)
    f2 = U.open_src(os.path.join(run, s2))
    fa = os.open('state.json', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600, dir_fd=f2)
    os.write(fa, b'{}')
    os.close(fa)
    os.close(f2)
    rdb2 = RDB()

    def active():
        f = copy.deepcopy(facts())
        f.update(series=s2, svc=dict(f['svc'], ActiveState='active'))
        return f
    r = U.seal_unstarted(s2, LID, real_deps(rdb2, series=s2, collect=active))
    case(FS_CASES[8], r['status'] == 'BLOCKED_SESSION_UNKNOWN' and rdb2.calls == []
         and not os.path.exists(os.path.join(SEAL, s2, '1')))

    s3 = 'b10s3'
    os.mkdir(os.path.join(run, s3), 0o750)
    f3 = U.open_src(os.path.join(run, s3))
    fa = os.open('state.json', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600, dir_fd=f3)
    os.write(fa, b'{}')
    os.close(fa)
    os.close(f3)
    rdb3, n = RDB(), {'n': 0}

    def flaky():
        n['n'] += 1     # 1-й вызов — после заморозки (до proof), 2-й — после печати: маска пропала
        f = facts()
        return {'svc': f['svc'], 'mask': f['mask'] if n['n'] == 1 else dict(f['mask'], LoadState='loaded')}

    def s3facts():
        f = facts()
        f.update(series=s3, state=dict(f['state'], series=s3), anchor=dict(f['anchor'], series=s3),
                 lease_row=dict(f['lease_row'], holder_session='zprobe-' + s3))
        return f
    r = U.seal_unstarted(s3, LID, real_deps(rdb3, series=s3, collect=s3facts, recheck=flaky))
    case(FS_CASES[9], r['status'] == 'BLOCKED_STOP_REVIEW' and r['seal'] == 'SEALED_NOW' and rdb3.row is not None
         and os.path.exists(os.path.join(SEAL, s3, '1', 'proof.json')))

if not OK:
    print('ZPROBE_UNSTARTED_TEST=FAIL')
    sys.exit(1)
print('ZPROBE_UNSTARTED_TEST=' + ('PASS' if SKIPPED == 0 else 'PASS_NO_ROOT'))
