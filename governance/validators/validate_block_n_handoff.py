#!/usr/bin/env python3
import json
from pathlib import Path
required = [
  'governance/reports/BEM945_FINAL_FOUNDATION_HANDOFF.md',
  'governance/state/operator_gate_boundary.json',
  'governance/state/roadmap_status_final.json',
  'governance/audit/BEM945_EXTERNAL_AUDIT_HANDOFF.md'
]
missing = [p for p in required if not Path(p).exists()]
if missing:
    raise SystemExit('MISSING: ' + ', '.join(missing))
boundary = json.loads(Path('governance/state/operator_gate_boundary.json').read_text(encoding='utf-8'))
assert boundary['status'] == 'OPERATOR_GATED_BOUNDARY_REACHED'
final = json.loads(Path('governance/state/roadmap_status_final.json').read_text(encoding='utf-8'))
assert final['foundation_blocks_completed'] == 14
assert final['release_pass'] is False
print('BEM-945 Block N handoff validator PASS')
