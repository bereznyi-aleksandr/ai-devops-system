#!/usr/bin/env python3
from pathlib import Path
required = [
  'governance/runners/event_writer.py',
  'governance/runners/managed_channel_consumer.py',
  'governance/state/channel_dead_letters.jsonl',
  'governance/state/managed_channel_processed.jsonl',
  'governance/state/managed_channel_consumer_status.json',
  'governance/tests/test_managed_channel_consumer.py'
]
missing = [p for p in required if not Path(p).exists()]
if missing:
    raise SystemExit('MISSING: ' + ', '.join(missing))
consumer = Path('governance/runners/managed_channel_consumer.py').read_text(encoding='utf-8')
for token in ['vertical_curator_to_curator','horizontal_verified_data_transfer','dead_letter','process_once']:
    if token not in consumer:
        raise SystemExit('MISSING TOKEN: ' + token)
print('BEM-936 Block E channel validator PASS')
