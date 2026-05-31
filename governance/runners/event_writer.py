#!/usr/bin/env python3
import json
import time
from pathlib import Path

EVENT_LOG = Path('governance/logs/event_log.jsonl')

def write_event(event):
    EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    item = dict(event)
    item.setdefault('created_at', time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    item.setdefault('status', 'completed')
    if 'event_id' not in item:
        item['event_id'] = 'EVT-' + str(int(time.time() * 1000))
    with EVENT_LOG.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(item, ensure_ascii=False) + '\n')
    return item

if __name__ == '__main__':
    write_event({'trace_id':'selftest','event_type':'event_writer_selftest','source':'event_writer','target':'event_log','proof_ref':'stdout'})
    print('event_writer PASS')
