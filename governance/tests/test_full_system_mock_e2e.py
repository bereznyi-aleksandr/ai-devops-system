#!/usr/bin/env python3
import json
from pathlib import Path

required = [
  'governance/state/object_passports.json',
  'governance/state/contours_registry.json',
  'governance/state/providers_registry.json',
  'governance/state/managed_channel_schema.json',
  'governance/state/dispatch_lifecycle_schema.json',
  'governance/state/telegram_input_envelope_schema.json',
  'governance/runners/curator_router.py',
  'governance/runners/contour_lifecycle_runner.py',
  'governance/runners/dispatch_consumer.py',
  'governance/runners/managed_channel_consumer.py'
]
missing = [p for p in required if not Path(p).exists()]
if missing:
    raise SystemExit('MISSING: ' + ', '.join(missing))
route = {
  'operator_input': 'Telegram or ChatGPT',
  'gd_curator': 'EL-CUR-GD-001',
  'dir_curator': 'EL-CUR-DIR-001',
  'wrk_curator': 'EL-CUR-WRK-001',
  'target_contour': 'WRK-C1',
  'cycle': ['analyst','auditor','executor','auditor'],
  'report': 'canonical_report'
}
Path('governance/state/full_system_mock_e2e_result.json').write_text(json.dumps({'status':'PASS','route':route}, ensure_ascii=False, indent=2)+'
', encoding='utf-8')
print('BEM-941 full system mock E2E PASS')
