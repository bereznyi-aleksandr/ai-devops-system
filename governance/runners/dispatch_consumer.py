#!/usr/bin/env python3
from pathlib import Path
import json
from datetime import datetime, timezone

QUEUE = Path('governance/state/dispatch_queue.jsonl')
PROCESSED = Path('governance/state/dispatch_processed.jsonl')
DEAD = Path('governance/state/dispatch_dead_letters.jsonl')
EVENT_LOG = Path('governance/logs/event_log.jsonl')
SCHEMA = Path('governance/state/dispatch_lifecycle_schema.json')


def append_jsonl(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(obj, ensure_ascii=False) + '
')


def load_schema():
    if SCHEMA.exists():
        return json.loads(SCHEMA.read_text(encoding='utf-8'))
    return {'required_fields': []}


def validate_item(item, schema):
    missing = [k for k in schema.get('required_fields', []) if k not in item]
    if missing:
        return False, 'missing_fields:' + ','.join(missing)
    if item.get('status') != 'queued':
        return False, 'not_queued:' + str(item.get('status'))
    if not item.get('proof_ref'):
        return False, 'missing_proof_ref'
    return True, 'ok'


def process_item(item, schema):
    now = datetime.now(timezone.utc).isoformat()
    ok, reason = validate_item(item, schema)
    if not ok:
        append_jsonl(DEAD, {'created_at': now, 'reason': reason, 'item': item})
        return {'status': 'dead_letter', 'reason': reason, 'dispatch_id': item.get('dispatch_id')}
    event = {
        'event_id': 'dispatch-' + str(item.get('dispatch_id')),
        'trace_id': item.get('trace_id'),
        'created_at': now,
        'event_type': 'role_activation_requested',
        'source': 'dispatch_consumer',
        'target': {'object': item.get('target_object'), 'contour': item.get('target_contour'), 'role': item.get('logical_role'), 'provider': item.get('provider_id')},
        'status': 'completed',
        'proof_ref': item.get('proof_ref'),
        'logical_role': item.get('logical_role'),
        'provider_id': item.get('provider_id'),
        'fallback_used': item.get('fallback_used'),
        'fallback_reason': item.get('fallback_reason')
    }
    append_jsonl(EVENT_LOG, event)
    processed = dict(item)
    processed['status'] = 'completed'
    processed['processed_at'] = now
    processed['event_ref'] = event['event_id']
    append_jsonl(PROCESSED, processed)
    return {'status': 'completed', 'dispatch_id': item.get('dispatch_id'), 'event_ref': event['event_id']}


def run_once():
    schema = load_schema()
    results = []
    if not QUEUE.exists():
        return {'processed': 0, 'results': []}
    for line in QUEUE.read_text(encoding='utf-8', errors='ignore').splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            append_jsonl(DEAD, {'created_at': datetime.now(timezone.utc).isoformat(), 'reason': 'invalid_json', 'line': line})
            results.append({'status': 'dead_letter', 'reason': 'invalid_json'})
            continue
        results.append(process_item(item, schema))
    return {'processed': len(results), 'results': results}

if __name__ == '__main__':
    print(json.dumps(run_once(), ensure_ascii=False))
