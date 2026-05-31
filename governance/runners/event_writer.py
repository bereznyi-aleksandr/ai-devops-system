#!/usr/bin/env python3
from pathlib import Path
import json
from datetime import datetime, timezone

EVENT_LOG = Path('governance/logs/event_log.jsonl')


def write_event(event):
    EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    event = dict(event)
    event.setdefault('created_at', datetime.now(timezone.utc).isoformat())
    required = ['event_id', 'trace_id', 'event_type', 'source', 'target', 'status', 'proof_ref']
    missing = [k for k in required if not event.get(k)]
    if missing:
        raise ValueError('missing event fields: ' + ', '.join(missing))
    with EVENT_LOG.open('a', encoding='utf-8') as f:
        f.write(json.dumps(event, ensure_ascii=False) + '
')
    return str(EVENT_LOG)

if __name__ == '__main__':
    write_event({
        'event_id': 'event-writer-selftest',
        'trace_id': 'event-writer-selftest',
        'event_type': 'selftest',
        'source': 'event_writer',
        'target': 'event_log',
        'status': 'completed',
        'proof_ref': 'stdout'
    })
    print('event_writer PASS')
