#!/usr/bin/env python3
from pathlib import Path
import json
from datetime import datetime, timezone

CHANNEL = Path('governance/state/managed_channel_messages.jsonl')
DEAD = Path('governance/state/channel_dead_letters.jsonl')
PROCESSED = Path('governance/state/managed_channel_processed.jsonl')
EVENT_LOG = Path('governance/logs/event_log.jsonl')
SCHEMA = Path('governance/state/managed_channel_schema.json')


def load_schema():
    if SCHEMA.exists():
        return json.loads(SCHEMA.read_text(encoding='utf-8'))
    return {'route_types': {}, 'required_fields': []}


def append_jsonl(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(obj, ensure_ascii=False) + '
')


def validate_message(msg, schema):
    missing = [k for k in schema.get('required_fields', []) if k not in msg]
    if missing:
        return False, 'missing_fields:' + ','.join(missing)
    route_type = msg.get('route_type')
    if route_type not in schema.get('route_types', {}):
        return False, 'unknown_route_type:' + str(route_type)
    return True, 'ok'


def process_message(msg, schema):
    ok, reason = validate_message(msg, schema)
    now = datetime.now(timezone.utc).isoformat()
    if not ok:
        dead = {'created_at': now, 'reason': reason, 'message': msg}
        append_jsonl(DEAD, dead)
        return {'status': 'dead_letter', 'reason': reason, 'message_id': msg.get('message_id')}
    event = {
        'event_id': 'evt-' + str(msg.get('message_id')),
        'trace_id': msg.get('trace_id'),
        'created_at': now,
        'event_type': msg.get('route_type'),
        'source': msg.get('source'),
        'target': msg.get('target'),
        'status': 'completed',
        'proof_ref': msg.get('proof_ref') or 'managed_channel_consumer'
    }
    append_jsonl(EVENT_LOG, event)
    processed = {'processed_at': now, 'message_id': msg.get('message_id'), 'trace_id': msg.get('trace_id'), 'route_type': msg.get('route_type'), 'event_ref': event['event_id']}
    append_jsonl(PROCESSED, processed)
    return {'status': 'completed', 'message_id': msg.get('message_id'), 'event_ref': event['event_id']}


def run_once():
    schema = load_schema()
    results = []
    if not CHANNEL.exists():
        return {'processed': 0, 'results': []}
    for line in CHANNEL.read_text(encoding='utf-8', errors='ignore').splitlines():
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except Exception as e:
            append_jsonl(DEAD, {'created_at': datetime.now(timezone.utc).isoformat(), 'reason': 'invalid_json', 'line': line})
            results.append({'status': 'dead_letter', 'reason': 'invalid_json'})
            continue
        results.append(process_message(msg, schema))
    return {'processed': len(results), 'results': results}

if __name__ == '__main__':
    print(json.dumps(run_once(), ensure_ascii=False))
