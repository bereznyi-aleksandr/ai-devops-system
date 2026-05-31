#!/usr/bin/env python3
import json
from pathlib import Path
required = [
  'governance/state/object_passports.json',
  'governance/state/contours_registry.json',
  'governance/state/providers_registry.json',
  'governance/state/contour_provider_policy.json',
  'governance/state/provider_failover_policy.json',
  'governance/state/workspace_policy.json'
]
missing = [p for p in required if not Path(p).exists()]
if missing:
    raise SystemExit('MISSING: ' + ', '.join(missing))
for p in required:
    json.loads(Path(p).read_text(encoding='utf-8'))
print('BEM-933 Block B foundation validator PASS')
