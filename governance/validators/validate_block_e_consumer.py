#!/usr/bin/env python3
import json
from pathlib import Path
required = [
  'governance/runners/event_writer.py',
  'governance/runners/managed_channel_consumer.py',
  'governance/state/managed_channel_schema.json',
  'governance/state/managed_channel_messages.jsonl'
]
missing = [p for p in required if not Path(p).exists()]
if missing:
    raise SystemExit('MISSING: ' + ', '.join(missing))
schema = json.loads(Path('governance/state/managed_channel_schema.json').read_text(encoding='utf-8'))
for rt in ['vertical_curator_to_curator','horizontal_verified_data_transfer']:
    assert rt in schema['route_types']
print('BEM-936 Block E consumer validator PASS')
