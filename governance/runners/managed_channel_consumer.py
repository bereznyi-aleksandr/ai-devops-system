#!/usr/bin/env python3
import json
import time
from pathlib import Path

CHANNEL = Path('governance/state/managed_channel_messages.jsonl')
DEAD = Path('governance/state/channel_dead_letters.jsonl')
OUT = Path('governance/state/managed_channel_processed.jsonl')
EVENT_LOG = Path('governance/logs/event_log.jsonl')

ALLOWED_ROUTE_TYPES = {
  'vertical_curator_to_curator',
  'contour_input',
  'proposal',
  'proposal_revision',
  'execution_approval',
  'execution_result',
  'result_revision',
  'contour_output',
  'horizontal_verified_data_transfer',
  'horizontal_verified_data_query'
}

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

def validate_message(msg):
    required = ['message_id','trace_id','source','target','route_type','payload']
    missing = [k for k in required if k not in msg]
    if missing:
        return False, 'missing:' + ','.join(missing)
    if msg.get('route_type') not in ALLOWED_ROUTE_TYPES:
        return False, 'invalid_route_type:' + str(msg.get('route_type'))
    return True, 'ok'

def process_once():
    if not CHANNEL.exists():
        return {'processed':0,'dead':0,'reason':'channel_missing'}
    processed = 0
    dead = 0
    for line in CHANNEL.read_text(encoding='utf-8', errors='ignore').splitlines():
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except Exception as exc:
            append_jsonl(DEAD, {'raw': line, 'error': 'json_parse_error', 'detail': str(exc)})
            dead += 1
            continue
        ok, reason = validate_message(msg)
        if not ok:
            msg['dead_reason'] = reason
            append_jsonl(DEAD, msg)
            dead += 1
            continue
        msg['processed_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        msg['status'] = 'completed'
        append_jsonl(OUT, msg)
        write_event(msg['trace_id'], msg['route_type'], msg['source'], msg['target'], msg.get('proof_ref','managed_channel_consumer'))
        processed += 1
    return {'processed': processed, 'dead': dead}

if __name__ == '__main__':
    print(json.dumps(process_once(), ensure_ascii=False))
