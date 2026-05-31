#!/usr/bin/env python3
# Static selftest specification for BEM-936.
# Runtime invocation is handled by CI/runner in later E2E phases.
from pathlib import Path
required = [
  'governance/runners/managed_channel_consumer.py',
  'governance/runners/event_writer.py',
  'governance/state/managed_channel_schema.json',
  'governance/state/contour_lifecycle_schema.json'
]
missing = [p for p in required if not Path(p).exists()]
if missing:
    raise SystemExit('MISSING: ' + ', '.join(missing))
text = Path('governance/runners/managed_channel_consumer.py').read_text(encoding='utf-8')
for token in ['vertical_curator_to_curator','horizontal_verified_data_transfer','channel_dead_letters.jsonl']:
    if token not in text:
        raise SystemExit('MISSING TOKEN: ' + token)
print('BEM-936 managed channel consumer static selftest PASS')
