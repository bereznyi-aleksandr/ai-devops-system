#!/usr/bin/env python3
import json
from pathlib import Path
required = [
  'governance/state/managed_channel_schema.json',
  'governance/state/contour_lifecycle_schema.json',
  'governance/state/event_log_schema.json',
  'governance/state/elements_prompt_migration_policy.json'
]
missing = [p for p in required if not Path(p).exists()]
if missing:
    raise SystemExit('MISSING: ' + ', '.join(missing))
for p in required:
    json.loads(Path(p).read_text(encoding='utf-8'))
channel = json.loads(Path('governance/state/managed_channel_schema.json').read_text(encoding='utf-8'))
assert 'vertical_curator_to_curator' in channel['route_types']
assert 'horizontal_verified_data_transfer' in channel['route_types']
lifecycle = json.loads(Path('governance/state/contour_lifecycle_schema.json').read_text(encoding='utf-8'))
statuses = [s['status'] for s in lifecycle['statuses']]
for s in ['proposal_approved','execution_started','result_approved','contour_result_ready']:
    assert s in statuses
print('BEM-935 Block D schema validator PASS')
