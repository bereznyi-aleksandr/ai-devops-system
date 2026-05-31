#!/usr/bin/env python3
import json
from pathlib import Path
required = [
  'governance/state/dispatch_lifecycle_schema.json',
  'governance/state/dispatch_trigger_policy.json',
  'governance/state/dispatch_queue.jsonl',
  'governance/runners/dispatch_consumer.py'
]
missing = [p for p in required if not Path(p).exists()]
if missing:
    raise SystemExit('MISSING: ' + ', '.join(missing))
schema = json.loads(Path('governance/state/dispatch_lifecycle_schema.json').read_text(encoding='utf-8'))
for field in ['target_object','target_contour','logical_role','provider_id','proof_ref']:
    assert field in schema['required_fields']
policy = json.loads(Path('governance/state/dispatch_trigger_policy.json').read_text(encoding='utf-8'))
assert policy['initial_mode'] == 'workflow_dispatch'
print('BEM-937 Block F dispatch validator PASS')
