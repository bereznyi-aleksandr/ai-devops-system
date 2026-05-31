#!/usr/bin/env python3
import json
from pathlib import Path
required = [
  'governance/state/telegram_e2e_status.json',
  'governance/tests/test_full_system_mock_e2e.py',
  'governance/tests/test_provider_failover_e2e.py',
  'governance/tests/test_managed_channel_e2e.py',
  'governance/tests/test_canonical_report.py',
  'governance/state/e2e_run_manifest.json'
]
missing = [p for p in required if not Path(p).exists()]
if missing:
    raise SystemExit('MISSING: ' + ', '.join(missing))
status = json.loads(Path('governance/state/telegram_e2e_status.json').read_text(encoding='utf-8'))
assert status['production_status'] is None
print('BEM-941 Block J E2E validator PASS')
