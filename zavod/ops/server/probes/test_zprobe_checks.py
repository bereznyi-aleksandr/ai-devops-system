#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_checks.py
# ВЕРСИЯ: v0.3 (выпуск B11)  СТАТУС: DRAFT
# v0.3 (2026-11-17 06:51 +02:00, Claude, терминал zavod; REL96B PATH=A): B01–B34 — узкие исключения H4/H5 B11 для
#   b9/pb1trial2: настоящие PIN = значения R0 v14, формула ED; позитив на пробном PIN; строгий путь без изменений;
#   T0/серия/b10 — без исключения; отрицательные H4 (дыра, повтор, иной SEQNUM_ID/загрузка, потеря lo/хвоста, BD,
#   старт/PID journald, нет Reexecuting, verify, loss) и H5 (7-я, 5 записей, повтор, иной _UID/_CMDLINE, подделка курсора).
# v0.2 (2026-11-15, терминал zavod, чат cb6b67c5): K41–K46 — курсоры прохода H5 (REL65 M-03, CI 113);
#   K47–K49 — срок чтения журнала на всё чтение (REL65 L-03).
# ДАТА СОЗДАНИЯ: 2026-11-14 23:36 +02:00  ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · напарник · 03» (d6c11f6b)
# НАЗНАЧЕНИЕ: проверки evaluate() из zprobe_checks.py (проект B10 v0.18 раздел 1.3): эталонные факты B10 и B9 проходят,
#   каждая проверка ломает ровно одно условие и ждёт отказ ровно этого H. Значения checks годятся для закрытой
#   схемы proof.json (zprobe_seal.check_proof). Без системы — идёт везде. Итог ZPROBE_CHECKS_TEST=PASS/FAIL.
import copy
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zprobe_checks as C  # noqa: E402
import zprobe_seal as Z  # noqa: E402

OK = True
LID = '0123abcd-0000-4000-8000-00000000c0de'
L = LID.replace('-', '')
BOOT = 'bc77431f' + '0' * 24
T0 = 1_794_600_000
CUR = f's={"a" * 32};i=1f;b={BOOT};m=2a;t=5f1;x=9'
CUR_F = f's={"a" * 32};i=10;b={BOOT};m=1a;t=5e0;x=7'      # первая запись прохода H5 (раньше якоря)
CUR_L = f's={"a" * 32};i=30;b={BOOT};m=3a;t=602;x=8'      # последняя запись прохода H5
SHA = 'f' * 64


def case(name, cond):
    global OK
    OK &= bool(cond)
    print('CASE', name, 'PASS' if cond else 'FAIL', flush=True)


def facts(fmt):
    s = 'pb1trial2' if fmt == 'b9' else 'b10s1'
    st = {'lease': L, 'lease_id': LID, 'dropin': f'/run/systemd/system/zagent@{L}.service.d/50-zprobe.conf'}
    if fmt == 'b10':
        st.update(series=s, runner='b10')
    an = {'series': s, 'lease': L, 'lease_id': LID, 'boot_id': BOOT}
    if fmt == 'b9':
        an.update(cursor_after=CUR, cursor_after_us=(T0 + 50) * 1000000)
    else:
        an.update(cursor=CUR, cursor_us=(T0 + 1) * 1000000)
    return {'fmt': fmt, 'series': s, 'lid': LID, 'boot_now': BOOT, 'btime': T0 - 3600,
            'lease_row': {'lease_id': LID, 'status': 'OPEN', 'holder_session': 'zprobe-' + s, 'opened_by': 'zprobe-run',
                          'role_key': '01_install_probe', 'opened_at_s': T0},
            'state': st, 'state_sha_run': SHA, 'state_sha_manifest': SHA if fmt == 'b9' else None,
            'evidence_lease': L, 'evidence_since_s': T0 - 5 if fmt == 'b9' else None, 'anchor': an,
            'anchor_cursor_ok': True,
            'unit_entries': {'start_jobs': [T0 - 10], 'lease_open': [T0 - 1] if fmt == 'b10' else [], 'boots': [BOOT]},
            'other_runner_count': 0,
            'fragment': {'path': f'/etc/systemd/system/zprobe-run-{fmt}@.service', 'sha': SHA, 'safe': True},
            'fragment_expected': {'path': f'/etc/systemd/system/zprobe-run-{fmt}@.service', 'sha': SHA},
            'first_entry_s': T0 - 3600 + 2, 'journald_active': 'active', 'journald_mono_us': 3_000_000, 'verify_rc': 0,
            'scan': {'rc': 0, 'n': 120, 'unit_hits': 0, 'start_hits': 0, 'loss': 0, 'other': 0, 'first_cursor': CUR_F,
                     'last_cursor': CUR_L},
            'db': {'session_start': 0, 'session_start_log': 0, 'gate_command': 0, 'live': 0}, 'named_files': 0,
            'svc': {'ActiveState': 'inactive', 'InvocationID': '', 'ActiveEnterTimestamp': ''},
            'mask': {'link': '/dev/null', 'LoadState': 'masked', 'UnitFileState': 'masked-runtime', 'etc_exists': False},
            'first_start_request_s': None}


def only(fmt, h, mutate):
    h = h if isinstance(h, list) else [h]
    f = facts(fmt)
    mutate(f)
    r = C.evaluate(f)
    if r['failed'] != h:
        print('  got', r['failed'], flush=True)
    return r['failed'] == h


for fmt in ('b10', 'b9'):
    r = C.evaluate(facts(fmt))
    case(f'K01 {fmt}: reference facts pass all H1-H10', r['ok'] and r['failed'] == [] and r['t0_utc'].endswith('Z'))
    names = ['a.json']
    pobj = {'version': 1, 'series': facts(fmt)['series'], 'lease_id': LID, 'boot_id': BOOT, 't0_utc': r['t0_utc'],
            'checks': C.proof_checks(r), 'journal_from_cursor': r['journal_from_cursor'],
            'journal_to_cursor': r['journal_to_cursor'],
            'sources': [{'name': 'a.json', 'sha256': hashlib.sha256(b'a').hexdigest(), 'size': 1}],
            'inventory_sha256': SHA, 'preserve_manifest_sha256': SHA if fmt == 'b9' else None,
            'tool_version': 'b10-0.1', 'created_utc': '2026-11-14T21:40:00Z'}
    case(f'K02 {fmt}: checks fit the closed proof schema (H9 src {"r1" if fmt == "b9" else "run"})',
         Z.check_proof(Z.canon(pobj), pobj['series'], LID, names)['checks']['H9']['src'] ==
         ('r1' if fmt == 'b9' else 'run'))

M = [
    ('K03', 'b10', 'H1', 'state.json with extra field', lambda f: f['state'].update(extra=1)),
    ('K04', 'b10', 'H1', 'runner b9 in a B10 state', lambda f: f['state'].update(runner='b9')),
    ('K05', 'b10', 'H1', 'holder of another series', lambda f: f['lease_row'].update(holder_session='zprobe-x')),
    ('K06', 'b9', 'H1', 'state sum differs from preserve MANIFEST', lambda f: f.update(state_sha_manifest='e' * 64)),
    ('K07', 'b9', ['H1', 'H9'], 'R1 anchor of another boot (state and anchor)', lambda f: f['anchor'].update(boot_id='d' * 32)),
    ('K08', 'b10', 'H2', 'no ZPROBE_LEASE_OPEN line', lambda f: f['unit_entries'].update(lease_open=[])),
    ('K09', 'b10', 'H2', 'two systemd start-job records', lambda f: f['unit_entries'].update(start_jobs=[T0 - 9, T0 - 8])),
    ('K10', 'b10', 'H2', 'lease-open line after T0', lambda f: f['unit_entries'].update(lease_open=[T0 + 1])),
    ('K11', 'b10', 'H2', 'records of the other runner (b9) exist', lambda f: f.update(other_runner_count=1)),
    ('K12', 'b10', 'H2', 'unit records in two boots', lambda f: f['unit_entries'].update(boots=[BOOT, 'd' * 32])),
    ('K13', 'b10', 'H2', 'FragmentPath sum differs from installed list', lambda f: f['fragment'].update(sha='e' * 64)),
    ('K14', 'b10', 'H2', 'fragment writable by group or others', lambda f: f['fragment'].update(safe=False)),
    ('K15', 'b9', 'H2', 'evidence.since before the start-job record', lambda f: f.update(evidence_since_s=T0 - 20)),
    ('K16', 'b9', 'H2', 'evidence.since missing', lambda f: f.update(evidence_since_s=None)),
    ('K54', 'b9', 'H2', 'records of zprobe-run-b10@pb1trial2 exist (CI 67)', lambda f: f.update(other_runner_count=1)),
    ('K55', 'b9', ['H1', 'H9'], 'R1 anchor.series of another series (CI 67)', lambda f: f['anchor'].update(series='pb1trial3')),
    ('K17', 'b10', ['H3', 'H4'], 'boot started after T0 (journald too)', lambda f: f.update(btime=T0 + 1, first_entry_s=T0 + 2)),
    ('K18', 'b10', 'H4', 'first boot entry later than btime+60', lambda f: f.update(first_entry_s=T0 - 3600 + 61)),
    ('K19', 'b10', 'H4', 'journald restarted after T0', lambda f: f.update(journald_mono_us=3601 * 1000000)),
    ('K20', 'b10', 'H4', 'journalctl --verify code 1', lambda f: f.update(verify_rc=1)),
    ('K21', 'b10', 'H4', 'journald loss message since T0', lambda f: f['scan'].update(loss=1)),
    ('K53', 'b10', 'H4', 'no journal of this boot after reboot (CI 14)', lambda f: f.update(first_entry_s=None)),
    ('K22', 'b10', 'H5', 'scan returned no records', lambda f: f['scan'].update(n=0)),
    ('K23', 'b10', 'H5', 'zagent unit seen in a unit field', lambda f: f['scan'].update(unit_hits=1)),
    ('K24', 'b10', 'H5', 'zagent-start line with the lease', lambda f: f['scan'].update(start_hits=1)),
    ('K25', 'b10', 'H5', 'lease mentioned outside the probe unit', lambda f: f['scan'].update(other=1)),
    ('K26', 'b10', 'H6', 'session_start row exists', lambda f: f['db'].update(session_start=1)),
    ('K27', 'b10', 'H6', 'db facts missing', lambda f: f.update(db=None)),
    ('K50', 'b10', 'H6', 'session_start_log row exists (CI 13)', lambda f: f['db'].update(session_start_log=1)),
    ('K28', 'b10', 'H7', 'start request file named with the lease', lambda f: f.update(named_files=1)),
    ('K29', 'b10', 'H8', 'InvocationID not empty', lambda f: f['svc'].update(InvocationID='ab' * 16)),
    ('K30', 'b10', 'H9', 'anchor_run of another lease', lambda f: f['anchor'].update(lease_id=LID[:-1] + 'f')),
    ('K31', 'b10', 'H9', 'anchor_run cursor no longer readable', lambda f: f.update(anchor_cursor_ok=False)),
    ('K32', 'b10', 'H9', 'anchor_run later than the first start request', lambda f: f.update(first_start_request_s=T0)),
    ('K33', 'b9', 'H9', 'R1 anchor older than T0', lambda f: f['anchor'].update(cursor_after_us=(T0 - 1) * 1000000)),
    ('K51', 'b10', ['H5', 'H9'], 'anchor_run.json missing (CI 56)', lambda f: f.update(anchor=None)),
    ('K52', 'b9', ['H1', 'H5', 'H9'], 'R1 anchor file missing (CI 56)', lambda f: f.update(anchor=None)),
    ('K34', 'b10', 'H10', 'mask link not /dev/null', lambda f: f['mask'].update(link='/etc/x')),
    ('K35', 'b10', 'H10', 'object in /etc/systemd/system', lambda f: f['mask'].update(etc_exists=True)),
    ('K36', 'b10', 'H10', 'UnitFileState masked (persistent) instead of masked-runtime',
     lambda f: f['mask'].update(UnitFileState='masked')),
]
for code, fmt, h, what, mut in M:
    case(f'{code} {fmt}: {what} -> only {h} fails', only(fmt, h, mut))

f = facts('b10')
f['series'] = 'pb1trial2'
case('K37 B10 checker refuses series pb1trial2 (B9 residue name)', C.evaluate(f)['failed'] == ['ARGS'])
f = facts('b9')
f['series'] = 'b10s1'
case('K38 B9 checker accepts only pb1trial2', C.evaluate(f)['failed'] == ['ARGS'])
f = facts('b10')
del f['scan']
r = C.evaluate(copy.deepcopy(f))
case('K39 missing scan facts -> H4 and H5 fail, no exception', r['failed'] == ['H4', 'H5'])
try:
    C.proof_checks(C.evaluate(dict(facts('b10'), named_files=2)))
    raised = False
except ValueError:
    raised = True
case('K40 proof_checks refuses a failed evaluation', raised)

# REL65 M-03: proof.from — первая запись прохода H5, а не курсор якоря; якорь внутри [from, to]
for fmt in ('b10', 'b9'):
    r = C.evaluate(facts(fmt))
    case(f'K41 {fmt}: early H5 record before the anchor -> proof.from is that record, not the anchor',
         r['ok'] and r['journal_from_cursor'] == CUR_F and r['journal_to_cursor'] == CUR_L)
M2 = [
    ('K42', 'H5', 'first H5 cursor after the anchor (from replaced by a later one)',
     lambda f: f['scan'].update(first_cursor=CUR_F.replace('i=10', 'i=20'))),
    ('K43', 'H5', 'last H5 cursor before the anchor', lambda f: f['scan'].update(last_cursor=CUR_L.replace('i=30', 'i=1e'))),
    ('K44', 'H5', 'first H5 cursor of another boot', lambda f: f['scan'].update(first_cursor=CUR_F.replace(BOOT, 'd' * 32))),
    ('K45', 'H5', 'first H5 cursor of another journal file (s=)',
     lambda f: f['scan'].update(first_cursor=CUR_F.replace('a' * 32, 'c' * 32))),
    ('K46', 'H5', 'first H5 cursor missing', lambda f: f['scan'].update(first_cursor=None)),
]
for code, h, what, mut in M2:
    case(f'{code} b10: {what} -> only {h} fails', only('b10', h, mut))

# REL65 L-03: срок чтения журнала — на всё чтение, зависший journalctl убивается
import time  # noqa: E402
for code, what, prog in (
        ('K47', 'journalctl hangs inside a line without newline',
         'import sys,time; sys.stdout.write(\'{"a": 1\'); sys.stdout.flush(); time.sleep(60)'),
        ('K48', 'journalctl hangs after full lines without end of output',
         'import sys,time; sys.stdout.write(\'{"__CURSOR": "x"}\\n\'); sys.stdout.flush(); time.sleep(60)')):
    C.JOURNALCTL = [sys.executable, '-c', prog]
    t = time.monotonic()
    got = C.journal_stream([], lambda e: None, timeout=2)
    dt = time.monotonic() - t
    case(f'{code} {what} -> code 124 in time ({dt:.1f} s)', got[0] == 124 and dt < 20)
C.JOURNALCTL = [sys.executable, '-c', 'import sys; sys.stdout.write(\'{"__CURSOR": "c1"}\\n{"__CURSOR": "c2"}\\n\')']
case('K49 normal finite output -> code 0, two records, last cursor', C.journal_stream([], lambda e: None, timeout=20) ==
     (0, 2, 'c2'))
C.JOURNALCTL = ['journalctl']

# B11 (REL96B PATH=A): узкие исключения H4/H5 только для b9/pb1trial2 с закреплённым T0. Настоящие PIN сняты с
# сервера (их записей здесь нет), поэтому проверки идут на пробном PIN TP, построенном из пробных записей тем же
# способом, что R0 v12/v14; отдельно сверяются настоящие значения PIN_B9 и формулы ED/BD/SD.
ORIG_PIN, ORIG_SHA = C.PIN_B9, C.PIN_SHA
case('B01 real PIN_B9 = values accepted in R0 v14 (REL87/REL89), PIN_SHA over the canonical JSON',
     ORIG_PIN == {'series': 'pb1trial2', 't0': 1794667569, 'sid': 'd3cdd7404a194a9dbeac067ca4900372',
                  'lo': 285041, 'hi': 329536, 'hj': 338444,
                  'bd': '9e851c6953367ea654cd8d5b1fbbaeaa831a2922cf171c0e24c41340d7cb2148',
                  'sd': '4c61d994cf89b4c4b64a73f63819e9984c9e564fa444a045a3bf3735463152b4', 'self_n': 6,
                  'jd_start': 1794724116, 'jd_pid': '383173', 'jd_pids': ['323', '383173'],
                  'rx_from': 1794724105, 'rx_to': 1794724117}
     and ORIG_SHA == hashlib.sha256(__import__('json').dumps(ORIG_PIN, sort_keys=True, separators=(',', ':')).encode())
     .hexdigest())
import json  # noqa: E402
EX = {'__CURSOR': 'c', 'MESSAGE': 'привет', '_CMDLINE': 'runuser -u postgres', 'b': [1, 2]}
case('B02 entry_digest = R0 formula sha256(json.dumps(sort_keys, (",",":"), ensure_ascii)) incl. non-ASCII',
     C.entry_digest(EX) == hashlib.sha256(json.dumps(EX, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
                                         .encode()).hexdigest())
SID = 'e' * 32
LO, HI, HJ = 1000, 1005, 1010
H = C._h


def jent(n, **kw):
    e = {'__CURSOR': f's={SID};i={n:x};b={BOOT};m=1;t=1;x=1', '__SEQNUM': str(n), '__SEQNUM_ID': SID, '_BOOT_ID': BOOT}
    e.update(kw)
    return e


ENT = [jent(n) for n in range(LO, HJ + 3)]


def bd_of(ents):
    c = {int(e['__SEQNUM']): H(e['__CURSOR'])[:32] for e in ents if int(e['__SEQNUM']) in (LO, HI, HJ)}
    return H('%s|%d|%s|%d|%s|%d|%s' % (SID, LO, c[LO], HI, c[HI], HJ, c[HJ]))


SELF = [{'__CURSOR': f's={SID};i={n:x};b={BOOT};m=9;t=9;x=9', '_SYSTEMD_UNIT': 'session-1514.scope', '_UID': '0',
         '_COMM': 'runuser', 'SYSLOG_IDENTIFIER': 'runuser', '_CMDLINE': f'runuser -u postgres -- psql -d bem {LID}',
         'MESSAGE': 'pam_unix(runuser:session): session ' + ('opened' if n % 2 else 'closed') + ' for user postgres'}
        for n in range(LO + 1, LO + 7)]


def oed(e):
    return H(e['__CURSOR'])[:32] + ':' + C.entry_digest(e)


OED = [oed(e) for e in SELF]
TP = dict(ORIG_PIN, t0=T0, sid=SID, lo=LO, hi=HI, hj=HJ, bd=bd_of(ENT), sd=H(' '.join(sorted(OED))),
          jd_start=T0 + 500, jd_pid='4242', jd_pids=['77', '4242'])


def seq_of(ents):
    q = C.seq_new()
    for e in ents:
        C.seq_add(q, e, BOOT, (LO, HI, HJ))
    return C.seq_summary(q)


def alt(f, ents=None, oe=None, other=6):
    f['journald_mono_us'] = (T0 + 500 - f['btime']) * 1000000
    f['journald_restart'] = {'main_pid': '4242', 'pids': ['77', '4242'], 'rx': 1}
    f['scan'].update(other=other, other_ed=list(OED if oe is None else oe), seq=seq_of(ENT if ents is None else ents))


C.PIN_B9, C.PIN_SHA = TP, H('test-pin')
f = facts('b9')
alt(f)
r = C.evaluate(f)
v4, v5 = r['checks']['H4']['value'], r['checks']['H5']['value']
case('B03 b9/pb1trial2 pinned: journald restarted after T0 + continuous journal + exactly the 6 pinned records -> all OK, '
     'values carry alt=R0V14 pin= and al=6 un=0, proof value schema accepts them',
     r['ok'] and ' alt=R0V14 pin=' in v4 and ' al=6 un=0 alt=R0V14 pin=' in v5 and Z.VALUE.fullmatch(v4)
     and Z.VALUE.fullmatch(v5))
r = C.evaluate(facts('b9'))
case('B04 b9 strict path (journald before T0, other=0) unchanged: OK without alt tokens',
     r['ok'] and 'alt=' not in r['checks']['H4']['value'] and 'alt=' not in r['checks']['H5']['value'])
case('B05 same pinned facts but T0 differs from PIN -> H4,H5 fail (no exception)',
     only('b9', ['H4', 'H5'], lambda f: (alt(f), f['lease_row'].update(opened_at_s=T0 + 1))))
case('B06 same facts in b10 -> H4,H5 fail (exceptions never apply to b10)', only('b10', ['H4', 'H5'], alt))
C.PIN_B9 = dict(TP, series='pb1trial9')
case('B07 PIN for another series -> pb1trial2 gets no exception', only('b9', ['H4', 'H5'], alt))
C.PIN_B9 = TP
gap = [e for e in ENT if int(e['__SEQNUM']) != 1003]
NEG = [
    ('B08', ['H4', 'H5'], 'journal gap (one __SEQNUM missing)', lambda f: alt(f, gap)),
    ('B09', ['H4', 'H5'], 'duplicated __SEQNUM', lambda f: alt(f, ENT + [ENT[3]])),
    ('B10', ['H4', 'H5'], 'record of another __SEQNUM_ID', lambda f: alt(f, ENT + [jent(HJ + 3, __SEQNUM_ID='f' * 32)])),
    ('B11', ['H4', 'H5'], 'record of another boot', lambda f: alt(f, ENT[:-1] + [jent(HJ + 2, _BOOT_ID='d' * 32)])),
    ('B12', ['H4', 'H5'], 'journal starts after lo (lo record lost)', lambda f: alt(f, ENT[1:])),
    ('B13', ['H4', 'H5'], 'journal ends before hj (tail lost)', lambda f: alt(f, [e for e in ENT if int(e['__SEQNUM']) < HJ])),
    ('B14', ['H4', 'H5'], 'anchor hi has another cursor (BD mismatch)',
     lambda f: alt(f, [jent(n, __CURSOR=f's={SID};i={n:x};b={BOOT};m=2;t=1;x=1') if n == HI else jent(n)
                       for n in range(LO, HJ + 3)])),
    ('B15', ['H4', 'H5'], 'seq facts missing', lambda f: (alt(f), f['scan'].pop('seq'))),
    ('B16', 'H4', 'journald start differs from PIN by 1 s', lambda f: (alt(f), f.update(journald_mono_us=f['journald_mono_us'] + 1000000))),
    ('B17', 'H4', 'journald MainPID differs', lambda f: (alt(f), f['journald_restart'].update(main_pid='4243'))),
    ('B18', 'H4', 'extra journald PID since T0', lambda f: (alt(f), f['journald_restart'].update(pids=['5', '77', '4242']))),
    ('B19', 'H4', 'no PID 1 Reexecuting in the PIN window', lambda f: (alt(f), f['journald_restart'].update(rx=0))),
    ('B20', 'H4', 'Reexecuting fact unreadable', lambda f: (alt(f), f['journald_restart'].update(rx=None))),
    ('B21', 'H4', 'journalctl --verify failed', lambda f: (alt(f), f.update(verify_rc=1))),
    ('B22', 'H4', 'journald loss message', lambda f: (alt(f), f['scan'].update(loss=1))),
    ('B23', 'H4', 'journald restart facts missing', lambda f: (alt(f), f.pop('journald_restart'))),
    ('B24', 'H5', 'a 7th foreign record', lambda f: alt(f, oe=OED + [oed(dict(SELF[0], MESSAGE='x'))], other=7)),
    ('B25', 'H5', 'only 5 foreign records (one pinned record missing)', lambda f: alt(f, oe=OED[:5], other=5)),
    ('B26', 'H5', 'the same pinned record twice instead of another', lambda f: alt(f, oe=OED[:5] + [OED[0]])),
    ('B27', 'H5', 'pinned record with another _UID', lambda f: alt(f, oe=OED[:2] + [oed(dict(SELF[2], _UID='1000'))] + OED[3:])),
    ('B28', 'H5', 'pinned record with another full _CMDLINE',
     lambda f: alt(f, oe=OED[:3] + [oed(dict(SELF[3], _CMDLINE=SELF[3]['_CMDLINE'] + ' -c x'))] + OED[4:])),
    ('B29', 'H5', 'look-alike runuser record with a forged cursor',
     lambda f: alt(f, oe=OED[:5] + [oed(dict(SELF[5], __CURSOR=SELF[5]['__CURSOR'].replace('x=9', 'x=8')))])),
    ('B30', 'H5', 'other counter 6 but digests missing', lambda f: (alt(f), f['scan'].update(other_ed=[]))),
    ('B31', 'H5', 'service trace (unit_hits) still fails with the exception', lambda f: (alt(f), f['scan'].update(unit_hits=1))),
    ('B32', 'H5', 'zagent-start trace still fails with the exception', lambda f: (alt(f), f['scan'].update(start_hits=1))),
]
for code, h, what, mut in NEG:
    case(f'{code} b9 pinned: {what} -> fails {h}', only('b9', h, mut))
q = C.seq_new()
C.seq_add(q, {'__CURSOR': 'c', '__SEQNUM': '0x3e8', '__SEQNUM_ID': SID, '_BOOT_ID': BOOT}, BOOT, (LO, HI, HJ))
C.seq_add(q, {'__CURSOR': 'd', '__SEQNUM_ID': SID, '_BOOT_ID': BOOT}, BOOT, (LO, HI, HJ))
s = C.seq_summary(q)
case('B33 seq_add: hex __SEQNUM parsed (0x3e8 = 1000, anchor lo), record without __SEQNUM counted as defect',
     s['min'] == 1000 and s['anchors'] == {'1000': [H('c')[:32]]} and s['dup'] == 1 and s['count'] == 1)
case('B34 seq_ok/self_ok with the REAL PIN refuse the test data', not C.seq_ok(seq_of(ENT), ORIG_PIN)
     and not C.self_ok(list(OED), ORIG_PIN))
C.PIN_B9, C.PIN_SHA = ORIG_PIN, ORIG_SHA

if not OK:
    print('ZPROBE_CHECKS_TEST=FAIL')
    sys.exit(1)
print('ZPROBE_CHECKS_TEST=PASS')
