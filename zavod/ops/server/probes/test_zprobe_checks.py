#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_checks.py
# ВЕРСИЯ: v0.2 (выпуск B10)  СТАТУС: DRAFT
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
    ('K17', 'b10', ['H3', 'H4'], 'boot started after T0 (journald too)', lambda f: f.update(btime=T0 + 1, first_entry_s=T0 + 2)),
    ('K18', 'b10', 'H4', 'first boot entry later than btime+60', lambda f: f.update(first_entry_s=T0 - 3600 + 61)),
    ('K19', 'b10', 'H4', 'journald restarted after T0', lambda f: f.update(journald_mono_us=3601 * 1000000)),
    ('K20', 'b10', 'H4', 'journalctl --verify code 1', lambda f: f.update(verify_rc=1)),
    ('K21', 'b10', 'H4', 'journald loss message since T0', lambda f: f['scan'].update(loss=1)),
    ('K22', 'b10', 'H5', 'scan returned no records', lambda f: f['scan'].update(n=0)),
    ('K23', 'b10', 'H5', 'zagent unit seen in a unit field', lambda f: f['scan'].update(unit_hits=1)),
    ('K24', 'b10', 'H5', 'zagent-start line with the lease', lambda f: f['scan'].update(start_hits=1)),
    ('K25', 'b10', 'H5', 'lease mentioned outside the probe unit', lambda f: f['scan'].update(other=1)),
    ('K26', 'b10', 'H6', 'session_start row exists', lambda f: f['db'].update(session_start=1)),
    ('K27', 'b10', 'H6', 'db facts missing', lambda f: f.update(db=None)),
    ('K26b', 'b10', 'H6', 'session_start_log row exists (CI 13)', lambda f: f['db'].update(session_start_log=1)),
    ('K28', 'b10', 'H7', 'start request file named with the lease', lambda f: f.update(named_files=1)),
    ('K29', 'b10', 'H8', 'InvocationID not empty', lambda f: f['svc'].update(InvocationID='ab' * 16)),
    ('K30', 'b10', 'H9', 'anchor_run of another lease', lambda f: f['anchor'].update(lease_id=LID[:-1] + 'f')),
    ('K31', 'b10', 'H9', 'anchor_run cursor no longer readable', lambda f: f.update(anchor_cursor_ok=False)),
    ('K32', 'b10', 'H9', 'anchor_run later than the first start request', lambda f: f.update(first_start_request_s=T0)),
    ('K33', 'b9', 'H9', 'R1 anchor older than T0', lambda f: f['anchor'].update(cursor_after_us=(T0 - 1) * 1000000)),
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

if not OK:
    print('ZPROBE_CHECKS_TEST=FAIL')
    sys.exit(1)
print('ZPROBE_CHECKS_TEST=PASS')
