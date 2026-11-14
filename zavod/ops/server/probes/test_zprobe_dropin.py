#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_dropin.py
# ВЕРСИЯ: v0.1 (выпуск B10)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-14 23:00 +02:00  ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · 09» (3037f186)
# НАЗНАЧЕНИЕ: проверки zprobe_dropin.py (проект B10 v0.18 раздел 2). Каждая проверка — одно нарушение.
#   Печатает CASE <имя> PASS/FAIL и итог ZPROBE_DROPIN_TEST=PASS/FAIL. Запуск: python3 -I test_zprobe_dropin.py
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zprobe_dropin as D  # noqa: E402

ALLOWED = {'ExecStart', 'ExecStartEx', 'DropInPaths'}
BASE = {'ExecStart': 'old', 'DropInPaths': '', 'User': 'zagent', 'MemoryMax': '3221225472'}
OK = True
ROOT = os.environ.get('ZPROBE_TEST_ROOT') or None


def case(name, cond):
    global OK
    OK &= bool(cond)
    print('CASE', name, 'PASS' if cond else 'FAIL')


def after(**kw):
    a = dict(BASE)
    a.update(kw)
    return a


def run(a, writer=None, logger=None, before=BASE):
    d = tempfile.mkdtemp(prefix='zdrop-', dir=ROOT)
    lines = []
    lg = logger or (lambda s: lines.append(s) or True)
    r = D.decide(before, a, ALLOWED, 'systemd 255', '2026-11-14T21:00:00Z', os.path.join(d, 'dropin_check.json'),
                 **({'writer': writer} if writer else {}), logger=lg)
    return r, lines, d


r, lines, d = run(after(ExecStart='new', DropInPaths='/run/x.conf'))
case('D01 only allowed keys -> OK, proceed', r['proceed'] and r['doc']['result'] == 'OK' and r['abort'] is None)
with open(os.path.join(d, 'dropin_check.json'), encoding='ascii') as f:
    disk = json.load(f)
case('D02 file written equals document', disk == r['doc'] and r['code'] == '-')
case('D03 file mode 0600', os.stat(os.path.join(d, 'dropin_check.json')).st_mode & 0o777 == 0o600
     or os.name != 'posix')
case('D04 Exec value redacted, no value and no hash', disk['values']['ExecStart'] == {
    'redacted': True, 'len_before': 3, 'len_after': 3} and 'new' not in json.dumps(disk))

r, lines, d = run(after(ExecStart='new', User='root'))
case('D05 extra key -> REFUSED, abort dropin_changed_other_props',
     not r['proceed'] and r['doc']['result'] == 'REFUSED' and r['abort'] == 'dropin_changed_other_props'
     and r['doc']['extra'] == ['User'])
case('D06 non-sensitive values kept before/after', r['doc']['values']['User'] == {'before': 'zagent', 'after': 'root'})
case('D07 log line: result, names, no values',
     lines == ['ZPROBE_DROPIN_CHECK result=REFUSED diag=OK code=- n=2 changed=ExecStart,User'])

r, lines, d = run(after(Environment='TOKEN=abc', ExecStart='new'))
case('D08 Environment redacted and secret not in log or file',
     r['doc']['values']['Environment'].get('redacted') is True and 'abc' not in json.dumps(r['doc'])
     and 'abc' not in lines[0])

r, lines, d = run(after(Description='x' * 600))
case('D09 value over 512 -> truncated, complete=false, STOP diag_overflow',
     r['doc']['values']['Description']['after_truncated'] is True and len(r['doc']['values']['Description']['after'])
     == 512 and not r['doc']['complete'] and r['doc']['result'] == 'STOP' and r['abort'] == 'diag_overflow'
     and not r['proceed'])
case('D10 log diag=INCOMPLETE when comparison incomplete', 'diag=INCOMPLETE' in lines[0])

many = {f'P{i}': str(i) for i in range(201)}
r, lines, d = run(dict(BASE, **many))
case('D11 over 200 changed names -> STOP diag_overflow', r['doc']['result'] == 'STOP' and not r['doc']['complete']
     and len(r['doc']['values']) == 200 and r['abort'] == 'diag_overflow')
case('D12 log line holds at most 40 names', len(lines[0].split('changed=')[1].split(',')) == 40)

r, lines, d = run(after(ExecStart='new', User='root'), writer=lambda p, b: 'ENOSPC')
case('D13 write fails on refusal -> still refusal, diag INCOMPLETE, code in log',
     r['abort'] == 'dropin_changed_other_props' and r['diag_status'] == 'DIAGNOSTICS_INCOMPLETE'
     and 'diag=INCOMPLETE code=ENOSPC' in lines[0] and r['exit_code'] is None)

r, lines, d = run(after(ExecStart='new'), writer=lambda p, b: 'sha_mismatch')
case('D14 OK comparison but file not written -> no start (dropin_check_unwritten)',
     not r['proceed'] and r['abort'] == 'dropin_check_unwritten')

r, lines, d = run(after(ExecStart='new', User='root'), writer=lambda p, b: 'EIO', logger=lambda s: False)
case('D15 file and log both lost -> exit code 75', r['exit_code'] == 75 and not r['proceed'])

r, lines, d = run(after(ExecStart='new', User='root'), logger=lambda s: False)
case('D16 log lost but file written -> no exit 75, still refusal', r['exit_code'] is None
     and r['abort'] == 'dropin_changed_other_props' and not r['logged'])

p = os.path.join(tempfile.mkdtemp(prefix='zdrop-', dir=ROOT), 'dropin_check.json')
open(p, 'w').close()
case('D17 existing file -> EEXIST, not overwritten', D.write_check(p, b'{}') == 'EEXIST' and os.path.getsize(p) == 0)

if os.name == 'posix':
    q = os.path.join(tempfile.mkdtemp(prefix='zdrop-', dir=ROOT), 'dropin_check.json')
    os.symlink('/dev/null', q)
    case('D18 symlink in place -> refused (EEXIST), target untouched', D.write_check(q, b'{}') == 'EEXIST')
else:
    case('D18 symlink in place -> refused (skipped: not posix)', True)

r, lines, d = run(after(**{'Bad Name;rm': '1', 'ExecStart': 'new'}))
case('D19 unsafe property name shown as ? in log', 'changed=?,ExecStart' in lines[0])

r, lines, d = run(dict(BASE))
case('D20 nothing changed -> OK with empty changed, log changed=-', r['proceed'] and r['doc']['changed'] == []
     and lines[0].endswith('n=0 changed=-'))

print('ZPROBE_DROPIN_TEST=' + ('PASS' if OK else 'FAIL'))
sys.exit(0 if OK else 1)
