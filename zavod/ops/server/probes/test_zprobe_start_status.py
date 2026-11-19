#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_start_status.py
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-19 12:31 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 12:31 +02:00
# ИСПОЛНИТЕЛЬ: Claude (терминал zavod, пускатель)
# НАЗНАЧЕНИЕ: офлайн-тесты итогов старта B15 (zprobe_start_status.py): все окна сбоя из REL151 п. 3 и REL152 п. 3 —
#   сбой до I и после I, задание без Q, Q без S, S до Q, S без E после смерти бегунка (inactive и failed), неверные
#   challenge и InvocationID, потеря I/Q/S, обрезанная и испорченная запись, нет ответа systemctl; «повтора нет».
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zprobe_start_status as T  # noqa: E402

OK, BAD = [], []
SER, CH, INV = 'pb1trial5', 'c' * 32, 'a' * 32


def case(name, got, want):
    good = got[0] == want
    (OK if good else BAD).append(name)
    print(('PASS ' if good else 'FAIL ') + f'{name} -> {got[0]} ({got[1]})', flush=True)


def raw(d):
    body = (json.dumps(d, sort_keys=True) + '\n').encode()
    return body + f'END len={len(body)} sha256={hashlib.sha256(body).hexdigest()}\n'.encode()


R = {'series': SER, 'challenge': CH}
I = T.parse_record('I', raw({'series': SER, 'challenge': CH}))
Q = T.parse_record('Q', raw({'series': SER, 'job': '4242'}))
S = T.parse_record('S', raw({'series': SER, 'challenge': CH, 'invocation_id': INV}))
E = T.parse_record('E', raw({'series': SER, 'challenge': CH, 'invocation_id': INV}))
ALIVE = {'active': 'activating', 'invocation': INV, 'job': False}
DEAD = {'active': 'inactive', 'invocation': '', 'job': False}
FAILED = {'active': 'failed', 'invocation': INV, 'job': False}
JOB = {'active': 'inactive', 'invocation': '', 'job': True}


def st(r=R, i=I, q=Q, s=(S,), e=(), unit=ALIVE):
    return T.classify(SER, {'R': r, 'I': i, 'Q': q, 'S': list(s), 'E': list(e)}, unit)


# Нормальный путь
case('T01 S and E same invocation -> TERMINAL', st(e=(E,), unit=DEAD), 'TERMINAL')
case('T02 S, unit alive, same invocation -> STARTED', st(), 'STARTED')
case('T03 I+Q, no S, unit activating -> QUEUED', st(s=()), 'QUEUED')
# Окна сбоя
case('T04 crash before I (R only, unit dead) -> DEAD', st(i=None, q=None, s=(), unit=DEAD), 'DEAD')
case('T05 crash after I before systemctl -> DEAD', st(q=None, s=(), unit=DEAD), 'DEAD')
case('T06 job queued but Q not written -> QUEUED', st(q=None, s=(), unit=JOB), 'QUEUED')
case('T07 Q written, runner died before S -> DEAD', st(s=(), unit=DEAD), 'DEAD')
case('T08 S before Q (Q lost after start) -> STARTED', st(q=None), 'STARTED')
case('T09 S without E, runner died, inactive -> FAILED_AFTER_START', st(unit=DEAD), 'FAILED_AFTER_START')
case('T10 S without E, runner died, failed -> FAILED_AFTER_START', st(unit=FAILED), 'FAILED_AFTER_START')
case('T11 S without E, inactive but job queued -> UNKNOWN', st(unit=JOB), 'UNKNOWN')
case('T12 S without E, deactivating (ExecStopPost: cleanup, journal start) -> STARTED (v0.3)',
     st(unit={'active': 'deactivating', 'invocation': INV, 'job': False}), 'STARTED')
case('T12a S without E, runner inactive, journal unit active -> STARTED (v0.3)',
     st(unit=dict(DEAD, journal={'active': 'activating', 'job': False})), 'STARTED')
case('T12b S without E, runner inactive, journal job queued -> STARTED (v0.3)',
     st(unit=dict(DEAD, journal={'active': 'inactive', 'job': True})), 'STARTED')
case('T12c S without E, runner and journal inactive -> FAILED_AFTER_START (v0.3)',
     st(unit=dict(DEAD, journal={'active': 'inactive', 'job': False})), 'FAILED_AFTER_START')
case('T12d S with other invocation, journal alive, runner deactivating -> UNKNOWN (v0.3)',
     st(unit={'active': 'deactivating', 'invocation': 'f' * 32, 'job': False}), 'UNKNOWN')
# Противоречия
case('T13 S challenge differs from R -> UNKNOWN',
     st(s=(dict(S, challenge='d' * 32),)), 'UNKNOWN')
case('T14 I challenge differs from R -> UNKNOWN', st(i=dict(I, challenge='d' * 32), s=()), 'UNKNOWN')
case('T15 S invocation differs from live unit -> UNKNOWN', st(unit=dict(ALIVE, invocation='b' * 32)), 'UNKNOWN')
case('T16 E invocation differs from S -> UNKNOWN', st(e=(dict(E, invocation_id='b' * 32),), unit=DEAD), 'UNKNOWN')
case('T17 two S -> UNKNOWN', st(s=(S, S)), 'UNKNOWN')
case('T18 two E -> UNKNOWN', st(e=(E, E), unit=DEAD), 'UNKNOWN')
case('T19 record of another series -> UNKNOWN', st(s=(dict(S, series='pb1trial4'),)), 'UNKNOWN')
case('T20 no R -> UNKNOWN', st(r=None), 'UNKNOWN')
# Потеря записей
case('T21 I lost, S present -> UNKNOWN', st(i=None, q=None), 'UNKNOWN')
case('T22 I lost, Q present -> UNKNOWN', st(i=None, s=()), 'UNKNOWN')
case('T23 S lost, E present -> UNKNOWN', st(s=(), e=(E,), unit=DEAD), 'UNKNOWN')
# Повреждения
b = raw({'series': SER, 'challenge': CH, 'invocation_id': INV})
case('T24 truncated S (no END) -> UNKNOWN', st(s=(T.parse_record('S', b[:b.rfind(b'END')]),)), 'UNKNOWN')
case('T25 S cut inside END line -> UNKNOWN', st(s=(T.parse_record('S', b[:-5]),)), 'UNKNOWN')
case('T26 S byte flipped -> UNKNOWN', st(s=(T.parse_record('S', b.replace(b'pb1trial5', b'pb1trial6', 1)),)), 'UNKNOWN')
case('T27 I wrong length in END -> UNKNOWN',
     st(i=T.parse_record('I', raw(R).replace(b'END len=', b'END len=1')), s=()), 'UNKNOWN')
case('T28 Q not JSON -> UNKNOWN', st(q=T.parse_record('Q', b'x\nEND len=2 sha256=' + hashlib.sha256(b'x\n')
                                                           .hexdigest().encode() + b'\n'), s=()), 'UNKNOWN')
case('T29 S missing invocation_id -> UNKNOWN', st(s=(T.parse_record('S', raw(R)),)), 'UNKNOWN')
case('T30 empty file -> UNKNOWN', st(i=T.parse_record('I', b''), s=()), 'UNKNOWN')
case('T31 trailing bytes after END -> UNKNOWN', st(s=(T.parse_record('S', b + b'x'),)), 'UNKNOWN')
# systemd
case('T32 systemctl show no answer -> UNKNOWN', st(unit=None), 'UNKNOWN')
case('T33 R only, unit activating (not ours) -> UNKNOWN', st(i=None, q=None, s=()), 'UNKNOWN')
case('T34 I without S, unit active (oneshot never active) -> UNKNOWN',
     st(s=(), unit={'active': 'active', 'invocation': INV, 'job': False}), 'UNKNOWN')
# Только чтение: модуль не может ничего запустить или записать
with open(os.path.join(HERE, 'zprobe_start_status.py'), encoding='utf-8') as f:
    src = '\n'.join(ln for ln in f.read().splitlines() if not ln.lstrip().startswith('#'))   # код без комментариев
ro =not any(w in src for w in ('import subprocess', 'import os', 'open(', 'systemctl start', 'exec'))
(OK if ro else BAD).append('T35 read-only module')
print(('PASS ' if ro else 'FAIL ') + 'T35 read-only module (no subprocess, os, open, exec)')

print(f'ZPROBE_START_STATUS_TESTS {len(OK)}/{len(OK) + len(BAD)} ' + ('PASS' if not BAD else 'FAIL'))
sys.exit(1 if BAD else 0)
