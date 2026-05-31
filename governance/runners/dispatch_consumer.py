#!/usr/bin/env python3
import json
import time
from pathlib import Path

QUEUE = Path('governance/state/dispatch_queue.jsonl')
PROCESSED = Path('governance/state/dispatch_processed.jsonl')
DEAD = Path('governance/state/dispatch_dead_letters.jsonl')
EVENT_LOG = Path('governance/logs/event_log.jsonl')
PROVIDER_POLICY = Path('governance/state/contour_provider_policy.json')

ROLE_TO_PROVIDER = {
  'analyst': 'GPT-ANALYST',
  'auditor': 'CLAUDE-AUDITOR',
  'executor': 'CLAUDE-EXECUTOR'
}

FALLBACK_PROVIDER = 'GPT-CODEX-FALLBACK'


def append_jsonl(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + '\n')


def write_event(trace_id, event_type, source, target, proof_ref):
    append_jsonl(EVENT_LOG, {
      'event_id':'EVT-' + str(int(time.time() * 1000)),
      'trace_id': trace_id,
      'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
      'event_type': event_type,
      'source': source,
      'target': target,
      'status': 'completed',
      'proof_ref': proof_ref
    })


def normalize(item):
    obj = dict(item)
    role = obj.get('logical_role') or obj.get('role') or 'executor'
    obj['logical_role'] = role
    obj.setdefault('provider_id', ROLE_TO_PROVIDER.get(role, 'GPT-CODEX-FALLBACK'))
    obj.setdefault('provider_mode', 'primary')
    obj.setdefault('fallback_used', False)
    obj.setdefault('fallback_reason', None)
    obj.setdefault('status', 'queued')
    obj.setdefault('proof_ref', None)
    return obj


def validate(item):
    required = ['trace_id','target_object','target_contour','logical_role','provider_id','payload']
    missing = [k for k in required if k not in item]
    if missing:
        return False, 'missing:' + ','.join(missing)
    if item.get('fallback_used') and not item.get('fallback_reason'):
        return False, 'fallback_without_reason'
    return True, 'ok'


def process_once():
    if not QUEUE.exists():
        return {'processed':0,'dead':0,'reason':'queue_missing'}
    processed = 0
    dead = 0
    for line in QUEUE.read_text(encoding='utf-8', errors='ignore').splitlines():
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except Exception as exc:
            append_jsonl(DEAD, {'raw': line, 'error':'json_parse_error', 'detail': str(exc)})
            dead += 1
            continue
        item = normalize(raw)
        ok, reason = validate(item)
        if not ok:
            item['dead_reason'] = reason
            item['status'] = 'dead_letter'
            append_jsonl(DEAD, item)
            dead += 1
            continue
        item['status'] = 'delivered'
        item['processed_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        append_jsonl(PROCESSED, item)
        write_event(item['trace_id'], 'role_activation_requested', 'dispatch_consumer', item['provider_id'], item.get('proof_ref') or 'dispatch_consumer')
        processed += 1
    return {'processed': processed, 'dead': dead}


if __name__ == '__main__':
    print(json.dumps(process_once(), ensure_ascii=False))
