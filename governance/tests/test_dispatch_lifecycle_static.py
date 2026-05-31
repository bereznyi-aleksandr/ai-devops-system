#!/usr/bin/env python3
from pathlib import Path
required = [
  'governance/state/dispatch_lifecycle_schema.json',
  'governance/runners/dispatch_consumer.py',
  'governance/state/dispatch_processed.jsonl',
  'governance/state/dispatch_dead_letters.jsonl',
  'governance/state/dispatch_consumer_status.json'
]
missing = [p for p in required if not Path(p).exists()]
if missing:
    raise SystemExit('MISSING: ' + ', '.join(missing))
consumer = Path('governance/runners/dispatch_consumer.py').read_text(encoding='utf-8')
for token in ['provider_id','logical_role','fallback_reason','role_activation_requested']:
    if token not in consumer:
        raise SystemExit('MISSING TOKEN: ' + token)
print('BEM-937 dispatch lifecycle static test PASS')
