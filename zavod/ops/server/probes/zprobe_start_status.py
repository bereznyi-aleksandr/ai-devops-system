#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_start_status.py
# ВЕРСИЯ: v0.3  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-19 12:31 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 14:20 +02:00
# v0.3 (интеграция B15): SERIES_END пишет служба журнала zprobe-journal-b15@, которую бегунок запускает в ExecStopPost.
#   Поэтому служба «жива» и в состоянии deactivating (идёт уборка ExecStopPost), а S без E при мёртвом бегунке, но живой
#   службе журнала или её задании — STARTED (S_runner_done_journal_pending), не FAILED_AFTER_START. unit['journal'] =
#   {'active', 'job'} — состояние службы журнала; нет поля — как в v0.2 (службы журнала нет).
# v0.2: PENDING — файл данных без признака готовности .ok (часть C v0.4, читает zprobe_recstore.py): служба жива —
#   записи ещё нет; служба не жива — UNKNOWN.
# ИСПОЛНИТЕЛЬ: Claude (терминал zavod, пускатель)
# НАЗНАЧЕНИЕ: B15, итог «zprobe-start --status» по записям старта (проект DECISION_B15_PUSH_AND_START v0.2/v0.3 часть B,
#   модель принята аудитом ChatGPT REL152: M-355-REL150-02 и M-355-REL151-02 CLOSED). Только чтение: функция classify()
#   ничего не запускает и не пишет. Записи: R (RESERVED в журнале серии), I (намерение до systemctl), Q (очередь после
#   systemctl start --no-block), S (первая запись бегунка), E (SERIES_END). Формат файлов I, Q, S — одна строка JSON и
#   последняя строка «END len=<N> sha256=<X>» (часть C, на аудите REL153); неполная или испорченная запись — UNKNOWN.
# ОГРАНИЧЕНИЯ: итог TERMINAL — не PASS; приёмка только после Б5–Б7. Повторного запуска нет ни при каком итоге.
import hashlib
import json
import re

STATES = ('TERMINAL', 'STARTED', 'QUEUED', 'DEAD', 'FAILED_AFTER_START', 'UNKNOWN')
CORRUPT = 'CORRUPT'
ALIVE = ('activating', 'active', 'reloading', 'deactivating')   # v0.3: deactivating — идёт ExecStopPost (уборка, журнал)
PENDING = 'PENDING'
_END = re.compile(rb'END len=(\d+) sha256=([0-9a-f]{64})\n\Z')
_NEED = {'I': ('series', 'challenge'), 'Q': ('series', 'job'), 'S': ('series', 'challenge', 'invocation_id'),
         'E': ('series', 'challenge', 'invocation_id'), 'R': ('series', 'challenge')}


def parse_record(kind, raw):
    """Байты файла записи → dict или CORRUPT. None (файла нет) → None. Длина и SHA-256 сверяются со строкой END."""
    if raw is None:
        return None
    if not isinstance(raw, bytes):
        return CORRUPT
    cut = raw.rfind(b'END len=')
    if cut <= 0 or raw[cut - 1:cut] != b'\n':
        return CORRUPT
    m = _END.match(raw[cut:])
    body = raw[:cut]
    if not m or int(m.group(1)) != len(body) or hashlib.sha256(body).hexdigest().encode() != m.group(2):
        return CORRUPT
    try:
        rec = json.loads(body.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        return CORRUPT
    if not isinstance(rec, dict) or any(not isinstance(rec.get(k), str) or not rec.get(k) for k in _NEED[kind]):
        return CORRUPT
    return rec


def classify(series, rec, unit):
    """rec: {'R': dict|None|CORRUPT, 'I': …, 'Q': …, 'S': [dict…] (все записи START бегунка), 'E': [dict…]}.
    unit: {'active': ActiveState, 'invocation': InvocationID, 'job': bool} или None (systemctl show не ответил).
    → (итог, причина). Порядок: противоречия и повреждения → UNKNOWN раньше любых других итогов."""
    R, I, Q = rec.get('R'), rec.get('I'), rec.get('Q')
    S_all, E_all = rec.get('S') or [], rec.get('E') or []
    if unit is None or not isinstance(unit, dict) or unit.get('active') is None:
        return 'UNKNOWN', 'systemctl_no_answer'
    jrn = unit.get('journal') if isinstance(unit.get('journal'), dict) else {}
    j_alive = jrn.get('active') in ALIVE or bool(jrn.get('job'))
    if PENDING in (R, I, Q) or PENDING in S_all + E_all:
        if unit.get('active') not in ALIVE and not j_alive:
            return 'UNKNOWN', 'data_without_ok_unit_not_alive'
        if R == PENDING:
            return 'UNKNOWN', 'R_without_ok'
        I, Q = (None if v == PENDING else v for v in (I, Q))
        S_all = [x for x in S_all if x != PENDING]
        E_all = [x for x in E_all if x != PENDING]
    for k, v in (('R', R), ('I', I), ('Q', Q)):
        if v == CORRUPT:
            return 'UNKNOWN', f'{k}_corrupt'
    if any(x == CORRUPT for x in S_all + E_all):
        return 'UNKNOWN', 'S_or_E_corrupt'
    if len(S_all) > 1:
        return 'UNKNOWN', 'two_S'
    if len(E_all) > 1:
        return 'UNKNOWN', 'two_E'
    S = S_all[0] if S_all else None
    E = E_all[0] if E_all else None
    for k, v in (('R', R), ('I', I), ('Q', Q), ('S', S), ('E', E)):
        if v is not None and v.get('series') != series:
            return 'UNKNOWN', f'{k}_other_series'
    if R is None:
        return 'UNKNOWN', 'no_R'
    if I is not None and I['challenge'] != R['challenge']:
        return 'UNKNOWN', 'I_challenge_differs'
    if Q is not None and I is None:
        return 'UNKNOWN', 'Q_without_I'
    if S is not None and I is None:
        return 'UNKNOWN', 'S_without_I'
    if S is not None and S['challenge'] != R['challenge']:
        return 'UNKNOWN', 'S_challenge_differs'
    if E is not None and S is None:
        return 'UNKNOWN', 'E_without_S'
    if E is not None and (E['invocation_id'] != S['invocation_id'] or E['challenge'] != S['challenge']):
        return 'UNKNOWN', 'E_differs_from_S'
    active, inv, job = unit.get('active'), unit.get('invocation') or '', bool(unit.get('job'))
    alive = active in ALIVE
    dead = active in ('inactive', 'failed') and not job
    if S is not None and alive and inv != S['invocation_id']:
        return 'UNKNOWN', 'S_invocation_differs_from_unit'
    if S is not None and E is not None:
        return 'TERMINAL', 'S_and_E'
    if S is not None:
        if alive:
            return 'STARTED', 'S_unit_alive'
        if dead and j_alive:
            return 'STARTED', 'S_runner_done_journal_pending'
        if dead:
            return 'FAILED_AFTER_START', 'S_without_E_unit_dead'
        return 'UNKNOWN', f'S_without_E_unit_{active}_job_{int(job)}'
    if I is not None:
        if active == 'activating' or job:
            return 'QUEUED', 'I_without_S_unit_activating_or_job'
        if dead:
            return 'DEAD', 'I_without_S_unit_dead'
        return 'UNKNOWN', f'I_without_S_unit_{active}'
    if dead:
        return 'DEAD', 'R_only_not_started'
    return 'UNKNOWN', f'R_only_unit_{active}_job_{int(job)}'
