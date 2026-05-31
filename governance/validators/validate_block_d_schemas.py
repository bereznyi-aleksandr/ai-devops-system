#!/usr/bin/env python3
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
    text = Path(p).read_text(encoding='utf-8')
    if len(text.strip()) < 10:
        raise SystemExit('EMPTY: ' + p)
channel = Path('governance/state/managed_channel_schema.json').read_text(encoding='utf-8')
for marker in ['vertical_curator_to_curator', 'horizontal_verified_data_transfer', 'contour_input']:
    if marker not in channel:
        raise SystemExit('MISSING marker: ' + marker)
lifecycle = Path('governance/state/contour_lifecycle_schema.json').read_text(encoding='utf-8')
for marker in ['proposal_approved', 'execution_started', 'result_approved', 'contour_result_ready']:
    if marker not in lifecycle:
        raise SystemExit('MISSING lifecycle marker: ' + marker)
print('BEM-935 Block D schema validator PASS')
