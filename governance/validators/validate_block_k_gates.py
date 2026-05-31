#!/usr/bin/env python3
import json
from pathlib import Path
required = [
  'governance/gates/production_operator_gate.json',
  'governance/gates/secret_names.md',
  'governance/gates/issue31_write_policy.md',
  'governance/gates/schedule_daemon_gate.md',
  'governance/gates/telegram_production_gate.md',
  'governance/gates/llm_runtime_gate.md'
]
missing = [p for p in required if not Path(p).exists()]
if missing:
    raise SystemExit('MISSING: ' + ', '.join(missing))
gate = json.loads(Path('governance/gates/production_operator_gate.json').read_text(encoding='utf-8'))
assert gate['status'] == 'OPERATOR_REQUIRED'
print('BEM-942 Block K gates validator PASS')
