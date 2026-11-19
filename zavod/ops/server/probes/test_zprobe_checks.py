#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_checks.py
# ВЕРСИЯ: v0.8 (выпуск B15)  СТАТУС: DRAFT  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 14:08 +02:00
# v0.8 (Claude, терминал zavod; выпуск B15): E01 — своя служба zprobe-run-b15@, чужие b9, b10, b13, b14; E03 — четыре чтения;
#   E14/E15 (новые) — записи и ошибка чтения zprobe-run-b14@.
# v0.7 (Claude, терминал zavod; выпуск B14): E01 — своя служба zprobe-run-b14@, чужие (b9, b10, b13); E03 — три отдельных
#   чтения; E12 — записи zprobe-run-b13@ дают счёт > 0; E13 — ошибка чтения zprobe-run-b13@ даёт None.
# v0.6 (Claude, терминал zavod; REL125 L-355-REL125-01): E01–E11 — units() (тип и состав служб для видов b10 и b9)
#   и other_runner_count(): каждая чужая служба читается отдельно с точными аргументами; записи b9, b10, обеих —
#   счёт > 0 и отказ H2; ошибка чтения любой из служб — None и отказ H2; вид b9 читает только zprobe-run-b10@.
# v0.5 (2026-11-17 17:33 +02:00, Claude, терминал zavod): B01 — настоящий PIN со значениями D14 (lid_sha, boot, lo0,
#   c0) и pin_complete(PIN_B9) = True; B37 — полный настоящий PIN не открывает исключение для пробных фактов иной
#   аренды и загрузки; B34 — настоящий PIN по-прежнему отвергает пробные данные.
# v0.4 (2026-11-17 07:51 +02:00, Claude, терминал zavod, помощник; REL97): B01/B34 — настоящий PIN с None в новых ключах
#   (lid_sha, boot, lo0, c0); пробный PIN TP заполнен; B03 — раскладка токенов obs/pin/bd/sd; B35–B58: закрыто при None
#   и неверном типе ключей PIN, другая аренда и загрузка при том же T0, H4 alt при other=0, lo0/c0, пропуск до T0,
#   факты неверного типа без исключения (точечно и перебором), obs меняется при подмене наблюдений, pin от них не зависит.
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


def case(name, cond, detail=''):
    global OK
    OK &= bool(cond)
    print('CASE', name, 'PASS' if cond else ('FAIL -> ' + str(detail)[:300] if detail else 'FAIL'), flush=True)


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
case('B01 real PIN_B9 = values accepted in R0 v14 (REL87/REL89) + D14 lid_sha/boot/lo0/c0, PIN_SHA over the canonical JSON',
     ORIG_PIN == {'series': 'pb1trial2', 't0': 1794667569, 'sid': 'd3cdd7404a194a9dbeac067ca4900372',
                  'lo': 285041, 'hi': 329536, 'hj': 338444,
                  'bd': '9e851c6953367ea654cd8d5b1fbbaeaa831a2922cf171c0e24c41340d7cb2148',
                  'sd': '4c61d994cf89b4c4b64a73f63819e9984c9e564fa444a045a3bf3735463152b4', 'self_n': 6,
                  'jd_start': 1794724116, 'jd_pid': '383173', 'jd_pids': ['323', '383173'],
                  'rx_from': 1794724105, 'rx_to': 1794724117,
                  'lid_sha': 'ef548a9ac3f3f45e6f0b8fd3c574738a2d6fa677bedcd17f5f36739b47b3c648',
                  'boot': 'bc77431fecfe48f88031169be02868da', 'lo0': 30356, 'c0': '671193ec161b0f94f03a8bdd2777ab2b'}
     and ORIG_SHA == hashlib.sha256(__import__('json').dumps(ORIG_PIN, sort_keys=True, separators=(',', ':')).encode())
     .hexdigest()
     and C.pin_complete(ORIG_PIN))
import json  # noqa: E402
EX = {'__CURSOR': 'c', 'MESSAGE': 'привет', '_CMDLINE': 'runuser -u postgres', 'b': [1, 2]}
case('B02 entry_digest = R0 formula sha256(json.dumps(sort_keys, (",",":"), ensure_ascii)) incl. non-ASCII',
     C.entry_digest(EX) == hashlib.sha256(json.dumps(EX, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
                                         .encode()).hexdigest())
SID = 'e' * 32
LO0, LO, HI, HJ = 995, 1000, 1005, 1010     # LO0 — первая запись загрузки (REL97 M-03), LO — якорь lo
H = C._h


def jent(n, **kw):
    e = {'__CURSOR': f's={SID};i={n:x};b={BOOT};m=1;t=1;x=1', '__SEQNUM': str(n), '__SEQNUM_ID': SID, '_BOOT_ID': BOOT}
    e.update(kw)
    return e


ENT = [jent(n) for n in range(LO0, HJ + 3)]


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
          jd_start=T0 + 500, jd_pid='4242', jd_pids=['77', '4242'],
          lid_sha=H(LID), boot=BOOT, lo0=LO0, c0=H(ENT[0]['__CURSOR'])[:32])


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
     'values carry alt=R0V14 obs= pin= (+bd/sd), proof value schema accepts them',
     r['ok'] and ' alt=R0V14 obs=' in v4 and ' OK alt=R0V14 obs=' in v5 and f' pin={H("test-pin")}' in v4
     and f' pin={H("test-pin")}' in v5 and Z.VALUE.fullmatch(v4) and Z.VALUE.fullmatch(v5))
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
    ('B12', ['H4', 'H5'], 'first record of the boot lost (journal starts after lo0)', lambda f: alt(f, ENT[1:])),
    ('B13', ['H4', 'H5'], 'journal ends before hj (tail lost)', lambda f: alt(f, [e for e in ENT if int(e['__SEQNUM']) < HJ])),
    ('B14', ['H4', 'H5'], 'anchor hi has another cursor (BD mismatch)',
     lambda f: alt(f, [jent(n, __CURSOR=f's={SID};i={n:x};b={BOOT};m=2;t=1;x=1') if n == HI else jent(n)
                       for n in range(LO0, HJ + 3)])),
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

# REL97 (REVISE 0/3/2): привязка к аренде и загрузке, сплошность от первой записи загрузки, наблюдения (obs), типы фактов
NEWKEYS = ('lid_sha', 'boot', 'lo0', 'c0')
H45 = ['H4', 'H5']


def altf(**kw):
    f = facts('b9')
    alt(f, **kw)
    return f


r = C.evaluate(altf())
case('B35 REL97 M-01: alt facts pass with the full test PIN (baseline for the None/type negatives)', r['ok'])
bad = []
for k in NEWKEYS:
    for v in (None, 5 if k != 'lo0' else '995', '', 'zz', True if k == 'lo0' else b'x'):
        C.PIN_B9 = dict(TP, **{k: v})
        if C.pinned_b9(facts('b9'), T0) or C.evaluate(altf())['failed'] != H45:
            bad.append((k, v))
C.PIN_B9 = TP
case('B36 REL97 M-01: any of lid_sha/boot/lo0/c0 None or of wrong type/format -> pinned_b9 False, exception not applied '
     '(H4,H5 fail, no exception)', not bad, bad)
C.PIN_B9 = ORIG_PIN
fa = altf()
case('B37 REL97 M-01: the REAL PIN (D14 values) is complete but never pins test facts of another lease/boot: pinned_b9 False, alt facts fail H4,H5',
     not C.pinned_b9(fa, T0) and C.evaluate(fa)['failed'] == H45 and C.pin_complete(ORIG_PIN))
C.PIN_B9 = TP
LID2 = '11111111-1111-4111-8111-111111111111'


def swap(f, a, b):
    return json.loads(json.dumps(f).replace(a, b))


f2 = swap(swap(fa, LID, LID2), L, LID2.replace('-', ''))
r2 = C.evaluate(f2)
case('B38 REL97 M-01: same T0, other lease_id (coherent facts) -> no exception, only H4,H5 fail (PIN bound to lid_sha)',
     f2['lid'] == LID2 and r2['failed'] == H45 and not C.pinned_b9(f2, T0))
f3 = swap(fa, BOOT, 'd' * 32)
r3 = C.evaluate(f3)
case('B39 REL97 M-01: same T0, other boot (coherent facts) -> no exception, only H4,H5 fail (PIN bound to boot)',
     r3['failed'] == H45 and not C.pinned_b9(f3, T0))
case('B40 REL97 M-01: H4 passed by alt and other=0 -> H5 fails (only H5), H4 stays OK',
     only('b9', 'H5', lambda f: alt(f, oe=[], other=0)))
rz = C.evaluate(altf(oe=[], other=0))
case('B41 REL97 M-01: same other=0 facts without journald restart (strict H4) still pass H5 strictly',
     C.evaluate(facts('b9'))['ok'] and rz['checks']['H4']['ok'] and not rz['checks']['H5']['ok'])
C.PIN_B9 = dict(TP, lo0=LO0 + 1)
case('B42 REL97 M-03: lo0 of PIN differs from the first record of the boot -> H4,H5 fail', only('b9', H45, alt))
C.PIN_B9 = dict(TP, c0='0' * 32)
case('B43 REL97 M-03: c0 of PIN differs from the cursor of the first record -> H4,H5 fail', only('b9', H45, alt))
C.PIN_B9 = TP
case('B44 REL97 M-03: first record has the right number but another cursor -> H4,H5 fail',
     only('b9', H45, lambda f: alt(f, [jent(LO0, __CURSOR=f's={SID};i={LO0:x};b={BOOT};m=7;t=1;x=1')] + ENT[1:])))
case('B45 REL97 M-03: number skipped BEFORE T0 (between lo0 and lo) -> H4,H5 fail',
     only('b9', H45, lambda f: alt(f, [e for e in ENT if int(e['__SEQNUM']) != LO0 + 2])))
case('B46 REL97 M-03: stream starts at lo (continuity only from T0, boot start unproven) -> H4,H5 fail',
     only('b9', H45, lambda f: alt(f, [e for e in ENT if int(e['__SEQNUM']) >= LO])))
sq_good = seq_of(ENT)
case('B47 REL97 M-03: seq summary of the whole boot has first=(lo0, SHA-256(cursor)[:32]) and passes seq_ok on the test PIN',
     sq_good['first'] == [LO0, H(ENT[0]['__CURSOR'])[:32]] and C.seq_ok(sq_good, TP))
qs = C.seq_new()
C.seq_add(qs, {'__CURSOR': 'c9', '_BOOT_ID': BOOT, '__SEQNUM_ID': SID}, BOOT, (LO, HI, HJ))
case('B48 REL97 M-03: first record without __SEQNUM is remembered as first=[None, ...] and counted as a defect',
     C.seq_summary(qs)['first'] == [None, H('c9')[:32]] and C.seq_summary(qs)['dup'] == 1)

BADSEQ = {
    'sids list': lambda s: s.update(sids=[SID]), 'sids None': lambda s: s.update(sids=None),
    'sids str': lambda s: s.update(sids=SID), 'anchors list': lambda s: s.update(anchors=[]),
    'anchors None': lambda s: s.update(anchors=None), 'anchors value not list': lambda s: s['anchors'].update({str(LO): 5}),
    'anchor cursor not str': lambda s: s['anchors'].update({str(LO): [None]}),
    'count str': lambda s: s.update(count=str(s['count'])), 'count None': lambda s: s.update(count=None),
    'uniq str': lambda s: s.update(uniq=str(s['uniq'])), 'uniq None': lambda s: s.update(uniq=None),
    'min str': lambda s: s.update(min=str(s['min'])), 'max None': lambda s: s.update(max=None),
    'dup str': lambda s: s.update(dup='0'), 'dup False': lambda s: s.update(dup=False),
    'boot_bad None': lambda s: s.update(boot_bad=None), 'first missing': lambda s: s.pop('first'),
    'first None': lambda s: s.update(first=None), 'first str': lambda s: s.update(first='x'),
    'first short': lambda s: s.update(first=[LO0]), 'first number str': lambda s: s.update(first=[str(LO0), s['first'][1]]),
    'first cursor int': lambda s: s.update(first=[LO0, 5]), 'seq not dict': None,
}
bad = []
for name, mut in BADSEQ.items():
    f = altf()
    if mut is None:
        f['scan']['seq'] = 'x'
    else:
        mut(f['scan']['seq'])
    try:
        got = C.evaluate(f)['failed']
    except Exception as e:  # noqa: BLE001
        got = repr(e)
    if got != H45:
        bad.append((name, got))
case('B49 REL97 L-01: wrong type or missing nested seq fact (sids/anchors/count/uniq/min/max/dup/boot_bad/first/cursor) '
     '-> stable FAIL H4,H5, no exception', not bad, bad)
bad = []
for name, mut, want in (
        ('other_ed str', lambda f: f['scan'].update(other_ed='abc'), ['H5']),
        ('other_ed None', lambda f: f['scan'].update(other_ed=None), ['H5']),
        ('other_ed ints', lambda f: f['scan'].update(other_ed=[1, 2, 3, 4, 5, 6]), ['H5']),
        ('other str', lambda f: f['scan'].update(other='6'), ['H5']),
        ('other True', lambda f: f['scan'].update(other=True), ['H5']),
        ('unit_hits False', lambda f: f['scan'].update(unit_hits=False), None),
        ('journald_restart str', lambda f: f.update(journald_restart='x'), ['H4']),
        ('journald_restart None', lambda f: f.update(journald_restart=None), ['H4']),
        ('journald_restart list', lambda f: f.update(journald_restart=[]), ['H4']),
        ('pids str', lambda f: f['journald_restart'].update(pids='77,4242'), ['H4']),
        ('rx str', lambda f: f['journald_restart'].update(rx='1'), ['H4']),
        ('scan str', lambda f: f.update(scan='x'), H45),
        ('anchor str', lambda f: f.update(anchor='x'), ['H1', 'H5', 'H9']),
        ('btime str', lambda f: f.update(btime='1'), ['H3', 'H4']),
        ('journald_mono str', lambda f: f.update(journald_mono_us='3'), ['H4']),
        ('lease_row str', lambda f: f.update(lease_row='x'), None),
        ('unit_entries list', lambda f: f.update(unit_entries=[]), None),
        ('fragment str', lambda f: f.update(fragment='x'), None),
        ('state list', lambda f: f.update(state=[]), None),
        ('db str', lambda f: f.update(db='x'), None),
        ('mask str', lambda f: f.update(mask='x'), None),
        ('svc str', lambda f: f.update(svc='x'), None),
        ('boots int', lambda f: f['unit_entries'].update(boots=5), None),
        ('start_jobs str', lambda f: f['unit_entries'].update(start_jobs='ab'), None)):
    f = altf()
    mut(f)
    try:
        got = C.evaluate(f)
        failed = got['failed']
        good = failed != [] if want is None else want == failed
    except Exception as e:  # noqa: BLE001
        failed, good = repr(e), False
    if not good:
        bad.append((name, failed))
case('B50 REL97 L-01: other_ed/other/journald_restart/scan/anchor/btime/lease_row/... of wrong type -> stable FAIL of the '
     'matching check, no exception', not bad, bad)
bad = []
JUNK = (None, 'x', 5, [], [1], {}, True, 1.5)
base = altf()
for k, v0 in base.items():
    for j in JUNK:
        f = copy.deepcopy(base)
        f[k] = j
        try:
            C.evaluate(f)
        except Exception as e:  # noqa: BLE001
            bad.append((k, j, repr(e)))
        if isinstance(v0, dict):
            for k2 in list(v0):
                f = copy.deepcopy(base)
                f[k][k2] = j
                try:
                    C.evaluate(f)
                    C.obs_json(f)
                except Exception as e:  # noqa: BLE001
                    bad.append((k, k2, j, repr(e)))
for j in JUNK:
    for key in ('fmt', 'series', 'lid'):
        f = dict(base, **{key: j})
        try:
            C.evaluate(f)
        except Exception as e:  # noqa: BLE001
            bad.append((key, j, repr(e)))
    for j2 in ('x', 5, [], None):
        try:
            C.evaluate(j2)
        except Exception as e:  # noqa: BLE001
            bad.append(('facts', j2, repr(e)))
case('B51 REL97 L-01: every top-level and second-level fact replaced by None/str/int/list/dict/bool/float -> evaluate '
     'and obs_json never raise', not bad, bad[:3])
f = copy.deepcopy(base)
f['lid'] = 5
case('B52 REL97 L-01: lid not a string -> stable ARGS, no exception', C.evaluate(f)['failed'] == ['ARGS'])

# REL97 M-02: наблюдения (obs) отдельно от закрепления (pin)
r = C.evaluate(base)
v4, v5 = r['checks']['H4']['value'], r['checks']['H5']['value']
t4, t5 = v4.split(' '), v5.split(' ')
kv4 = dict(x.split('=', 1) for x in t4 if '=' in x)
kv5 = dict(x.split('=', 1) for x in t5 if '=' in x)
obs_h = C.obs_sha(base)
seq_b = base['scan']['seq']
case('B53 REL97 M-02: H4 alt value = 8 tokens: gap verify loss OK alt obs= pin= bd=; obs differs from pin; bd is observed BD; '
     'schema accepts', len(t4) == 8 and 'OK' in t4 and 'alt=R0V14' in t4 and kv4['obs'] == obs_h
     and kv4['pin'] == H('test-pin') and kv4['obs'] != kv4['pin'] and kv4['bd'] == C.bd_observed(seq_b) == TP['bd']
     and Z.VALUE.fullmatch(v4) is not None, v4)
case('B54 REL97 M-02: H5 alt value = 8 tokens: n u oth OK alt obs= pin= sd=; sd is observed SD; schema accepts',
     len(t5) == 8 and 'OK' in t5 and 'alt=R0V14' in t5 and kv5['obs'] == obs_h and kv5['pin'] == H('test-pin')
     and kv5['sd'] == C.sd_observed(base['scan']['other_ed']) == TP['sd'] and kv5['oth'] == '6' and kv5['u'] == '0'
     and Z.VALUE.fullmatch(v5) is not None, v5)
obs = json.loads(C.obs_json(base))
case('B55 REL97 M-02: obs = SHA-256 of the canonical JSON (sort_keys, (",",":")) of seq summary, journald_restart, journald '
     'start (btime + mono//1e6), sorted other_ed, observed BD and SD', obs_h == hashlib.sha256(json.dumps(
         obs, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest() == H(C.obs_json(base))
     and obs['seq'] == seq_b and obs['jd'] == {'main_pid': '4242', 'pids': ['77', '4242'], 'rx': 1}
     and obs['jd_start'] == T0 + 500 and obs['other_ed'] == sorted(OED) and obs['bd'] == TP['bd']
     and obs['sd'] == TP['sd'] and obs['lid_sha'] == H(LID) and obs['boot'] == BOOT)
MUTOBS = {
    'seq.min': lambda f: f['scan']['seq'].update(min=f['scan']['seq']['min'] + 1),
    'seq.max': lambda f: f['scan']['seq'].update(max=f['scan']['seq']['max'] + 1),
    'seq.count': lambda f: f['scan']['seq'].update(count=f['scan']['seq']['count'] + 1),
    'seq.uniq': lambda f: f['scan']['seq'].update(uniq=f['scan']['seq']['uniq'] + 1),
    'seq.dup': lambda f: f['scan']['seq'].update(dup=1), 'seq.boot_bad': lambda f: f['scan']['seq'].update(boot_bad=1),
    'seq.sids': lambda f: f['scan']['seq']['sids'].update({'f' * 32: 1}),
    'seq.first number': lambda f: f['scan']['seq'].update(first=[LO0 + 1, f['scan']['seq']['first'][1]]),
    'seq.first cursor': lambda f: f['scan']['seq'].update(first=[LO0, '0' * 32]),
    'seq.anchor cursor': lambda f: f['scan']['seq']['anchors'].update({str(HI): ['0' * 32]}),
    'jd.main_pid': lambda f: f['journald_restart'].update(main_pid='1'),
    'jd.pids': lambda f: f['journald_restart'].update(pids=['1']), 'jd.rx': lambda f: f['journald_restart'].update(rx=2),
    'journald start (mono)': lambda f: f.update(journald_mono_us=f['journald_mono_us'] + 1000000),
    'btime': lambda f: f.update(btime=f['btime'] - 1),
    'other_ed element': lambda f: f['scan']['other_ed'].__setitem__(0, 'x' + f['scan']['other_ed'][0]),
    'other_ed count': lambda f: f['scan']['other_ed'].append('y'), 'other_n': lambda f: f['scan'].update(other=7),
    'scan n': lambda f: f['scan'].update(n=f['scan']['n'] + 1), 'lid': lambda f: f.update(lid=LID2),
    'boot': lambda f: f.update(boot_now='d' * 32),
}
bad = []
for name, mut in MUTOBS.items():
    f = copy.deepcopy(base)
    mut(f)
    if C.obs_sha(f) == obs_h:
        bad.append(name)
f = copy.deepcopy(base)
f['scan']['other_ed'].reverse()
case('B56 REL97 M-02: obs changes when ANY observed fact is replaced (seq, rx/PID, journald start, other_ed, lid, boot, n); '
     'order of other_ed does not matter (sorted)', not bad and C.obs_sha(f) == obs_h, bad)
fa2 = copy.deepcopy(base)
fa2['scan']['n'] += 1
ra2 = C.evaluate(fa2)
case('B57 REL97 M-02: pin= does not depend on observations: two passing runs with different observed n -> other obs=, '
     'same pin=', ra2['ok'] and ra2['checks']['H4']['value'].split('pin=')[1][:64] == H('test-pin')
     and ra2['checks']['H5']['value'].split('pin=')[1][:64] == H('test-pin') and C.obs_sha(fa2) != obs_h
     and ra2['checks']['H4']['value'] != v4)
pobj = {'version': 1, 'series': 'pb1trial2', 'lease_id': LID, 'boot_id': BOOT, 't0_utc': r['t0_utc'],
        'checks': C.proof_checks(r), 'journal_from_cursor': r['journal_from_cursor'],
        'journal_to_cursor': r['journal_to_cursor'],
        'sources': [{'name': 'a.json', 'sha256': hashlib.sha256(b'a').hexdigest(), 'size': 1}],
        'inventory_sha256': SHA, 'preserve_manifest_sha256': SHA, 'tool_version': 'b11-0.1',
        'created_utc': '2026-11-17T08:00:00Z'}
case('B58 REL97 M-02: proof with the alt values (obs= pin= bd= sd=) passes the closed proof schema check_proof',
     Z.check_proof(Z.canon(pobj), 'pb1trial2', LID, ['a.json'])['checks']['H4']['value'] == v4)
C.PIN_B9, C.PIN_SHA = ORIG_PIN, ORIG_SHA


# REL125 L-01: чужие службы пробы — отдельные чтения, отказ при ошибке любого (E01–E11)
S13 = 'pb1trial3'


def fake(counts, rcs=None):
    """Поток-заглушка journal_stream: counts/rcs по имени службы; запоминает аргументы каждого вызова."""
    calls = []

    def stream(args, each):
        calls.append(list(args))
        unit = args[1]
        for _ in range(counts.get(unit, 0)):
            each({'_SYSTEMD_UNIT': unit})
        return (rcs or {}).get(unit, 0), counts.get(unit, 0), None
    return stream, calls


U13, O13 = C.units('b10', S13)
case('E01 units b10: own zprobe-run-b15@, others (b9, b10, b13, b14) as a tuple',
     U13 == f'zprobe-run-b15@{S13}.service' and type(O13) is tuple
     and O13 == (f'zprobe-run-b9@{S13}.service', f'zprobe-run-b10@{S13}.service', f'zprobe-run-b13@{S13}.service',
                 f'zprobe-run-b14@{S13}.service'),
     (U13, O13))
U9, O9 = C.units('b9', 'pb1trial2')
case('E02 units b9 (frozen B12 R2): own zprobe-run-b9@, others only (b10,) — same units as v0.7',
     U9 == 'zprobe-run-b9@pb1trial2.service' and O9 == ('zprobe-run-b10@pb1trial2.service',), (U9, O9))
st, calls = fake({})
n = C.other_runner_count('b10', S13, st)
case('E03 no records of b9, b10, b13, b14: count 0, four separate reads with exact args',
     n == 0 and calls == [['-u', O13[0]], ['-u', O13[1]], ['-u', O13[2]], ['-u', O13[3]]], (n, calls))
st, _ = fake({O13[0]: 2})
case('E04 records of zprobe-run-b9@ only: count 2', C.other_runner_count('b10', S13, st) == 2)
st, _ = fake({O13[1]: 1})
case('E05 records of zprobe-run-b10@ only: count 1', C.other_runner_count('b10', S13, st) == 1)
st, _ = fake({O13[0]: 1, O13[1]: 3})
case('E06 records of both: count 4', C.other_runner_count('b10', S13, st) == 4)
st, _ = fake({}, {O13[0]: 1})
case('E07 read error of zprobe-run-b9@: None (not 0)', C.other_runner_count('b10', S13, st) is None)
st, _ = fake({O13[0]: 0}, {O13[1]: 124})
case('E08 read error (timeout 124) of zprobe-run-b10@: None (not 0)', C.other_runner_count('b10', S13, st) is None)
st, calls = fake({})
case('E09 kind b9 reads only zprobe-run-b10@pb1trial2',
     C.other_runner_count('b9', 'pb1trial2', st) == 0 and calls == [['-u', O9[0]]], calls)
case('E10 evaluate b10: other_runner_count None -> exactly H2 fails',
     only('b10', 'H2', lambda f: f.update(other_runner_count=None)))
case('E11 evaluate b10: other_runner_count 2 (b10 records) -> exactly H2 fails',
     only('b10', 'H2', lambda f: f.update(other_runner_count=2)))
st, _ = fake({O13[2]: 5})
case('E12 records of zprobe-run-b13@ only (B13 service ran this series): count 5',
     C.other_runner_count('b10', S13, st) == 5)
st, _ = fake({}, {O13[2]: 1})
case('E13 read error of zprobe-run-b13@: None (not 0)', C.other_runner_count('b10', S13, st) is None)
st, _ = fake({O13[3]: 3})
case('E14 records of zprobe-run-b14@ only (B14 service ran this series): count 3',
     C.other_runner_count('b10', S13, st) == 3)
st, _ = fake({}, {O13[3]: 1})
case('E15 read error of zprobe-run-b14@: None (not 0)', C.other_runner_count('b10', S13, st) is None)

if not OK:
    print('ZPROBE_CHECKS_TEST=FAIL')
    sys.exit(1)
print('ZPROBE_CHECKS_TEST=PASS')
