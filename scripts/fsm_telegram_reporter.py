#!/usr/bin/env python3
"""
FSM Telegram Report Mapper — E4-004
Читает events и формирует сообщения в telegram_outbox.jsonl
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTBOX = ROOT / 'governance/telegram_outbox.jsonl'
EXCHANGE = ROOT / 'governance/exchange.jsonl'
PROCESSED = ROOT / 'governance/processed_events.jsonl'

CHAT_ID = '601442777'

REPORT_EVENTS = {
    'ROLE_CYCLE_COMPLETED',
    'ROLE_CYCLE_BLOCKED',
    'ROLE_CYCLE_STEP_LIMIT_EXCEEDED',
    'PROVIDER_FAILOVER_SELECTED',
    'PROVIDER_FAILOVER_BLOCKED',
    'AUTONOMY_ENGINE_TASK_BLOCKED',
    'AUTONOMY_ENGINE_PRODUCTION_LOOP_DONE',
    'CURATOR_ROUTING_DECISION',
    'ROLE_ORCHESTRATOR_EMERGENCY_STOPPED',
}


def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def now_ua():
    from datetime import timedelta
    ua = datetime.now(timezone.utc) + timedelta(hours=3)
    return ua.strftime('%H:%M UA %d.%m')


def load_processed():
    if not PROCESSED.exists():
        return set()
    keys = set()
    for line in PROCESSED.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line:
            try:
                keys.add(json.loads(line).get('dedupe_key', ''))
            except Exception:
                pass
    return keys


def mark_processed(dedupe_key):
    PROCESSED.parent.mkdir(parents=True, exist_ok=True)
    entry = {'timestamp': now_iso(), 'dedupe_key': dedupe_key}
    with PROCESSED.open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def append_outbox(text, event_id=None):
    OUTBOX.parent.mkdir(parents=True, exist_ok=True)
    eid = event_id or ('fsm_report_' + uuid.uuid4().hex[:12])
    entry = {
        'event_id': eid,
        'timestamp': now_iso(),
        'target': 'operator',
        'channel': 'telegram',
        'chat_id': CHAT_ID,
        'text': text,
        'status': 'ready_to_send'
    }
    with OUTBOX.open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    return eid


def format_event(event):
    etype = event.get('type') or event.get('event', '')
    ts = event.get('timestamp', '')[:16]
    time_ua = now_ua()

    if etype == 'ROLE_CYCLE_COMPLETED':
        cycle = event.get('cycle_id', '?')
        return f"✅ FSM ЦИКЛ ЗАВЕРШЁН | {time_ua}\ncycle_id: {cycle}"

    if etype == 'ROLE_CYCLE_BLOCKED':
        reason = event.get('reason') or event.get('blocker') or '?'
        return f"🚫 FSM ЦИКЛ ЗАБЛОКИРОВАН | {time_ua}\nПричина: {str(reason)[:200]}"

    if etype == 'ROLE_CYCLE_STEP_LIMIT_EXCEEDED':
        cycle = event.get('cycle_id', '?')
        return f"⚠️ FSM ШАГ-ЛИМИТ | {time_ua}\ncycle_id: {cycle}"

    if etype == 'PROVIDER_FAILOVER_SELECTED':
        role = event.get('role', '?')
        provider = event.get('selected_provider', '?')
        return f"🔄 FAILOVER | {time_ua}\nРоль: {role} → провайдер: {provider}"

    if etype == 'PROVIDER_FAILOVER_BLOCKED':
        role = event.get('role', '?')
        return f"❌ FAILOVER ЗАБЛОКИРОВАН | {time_ua}\nРоль: {role} — нет доступных провайдеров"

    if etype == 'AUTONOMY_ENGINE_TASK_BLOCKED':
        task = event.get('task_id', '?')
        reason = event.get('reason', '?')
        return f"🚫 ДВИЖОК ЗАБЛОКИРОВАН | {time_ua}\nЗадача: {task}\n{str(reason)[:200]}"

    if etype == 'AUTONOMY_ENGINE_PRODUCTION_LOOP_DONE':
        completed = event.get('completed', [])
        pending = event.get('pending', [])
        blocker = event.get('blocker')
        status = '✅ без блокера' if not blocker else f'⚠️ {str(blocker)[:100]}'
        return (f"📊 PRODUCTION LOOP | {time_ua}\n"
                f"Выполнено: {len(completed)}\nОжидает: {len(pending)}\nСтатус: {status}")

    if etype == 'ROLE_ORCHESTRATOR_EMERGENCY_STOPPED':
        return f"🛑 EMERGENCY STOP АКТИВИРОВАН | {time_ua}"

    # Generic
    return f"📋 {etype} | {time_ua}"


def process_events(since_timestamp=None, max_events=20):
    """Read exchange.jsonl and queue reportable events to Telegram outbox."""
    if not EXCHANGE.exists():
        print('exchange.jsonl not found')
        return 0

    processed_keys = load_processed()
    queued = 0

    lines = EXCHANGE.read_text(encoding='utf-8', errors='replace').splitlines()
    for line in lines[-100:]:  # последние 100 событий
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except Exception:
            continue

        etype = event.get('type') or event.get('event', '')
        if etype not in REPORT_EVENTS:
            continue

        # Dedupe
        eid = event.get('event_id') or event.get('trace_id') or (etype + event.get('timestamp', ''))
        dedupe_key = f'fsm_report:{eid}'
        if dedupe_key in processed_keys:
            continue

        # Filter by timestamp if provided
        if since_timestamp and event.get('timestamp', '') < since_timestamp:
            continue

        text = format_event(event)
        outbox_id = append_outbox(text, eid)
        mark_processed(dedupe_key)
        processed_keys.add(dedupe_key)
        queued += 1
        print(f'Queued: {etype} → outbox {outbox_id}')

        if queued >= max_events:
            break

    return queued


if __name__ == '__main__':
    import sys
    since = sys.argv[1] if len(sys.argv) > 1 else None
    n = process_events(since_timestamp=since)
    print(f'QUEUED_TO_OUTBOX: {n}')
