#!/usr/bin/env python3
import json
from pathlib import Path
required = [
  'governance/state/telegram_input_envelope_schema.json',
  'governance/state/telegram_to_managed_channel_mapping.json',
  'governance/state/report_period_config.json',
  'governance/reports/templates/canonical_report_template.md',
  'governance/reports/templates/telegram_report_template.md',
  'governance/runners/telegram_input_mapper.py'
]
missing = [p for p in required if not Path(p).exists()]
if missing:
    raise SystemExit('MISSING: ' + ', '.join(missing))
schema = json.loads(Path('governance/state/telegram_input_envelope_schema.json').read_text(encoding='utf-8'))
assert schema['default_target_curator'] == 'EL-CUR-GD-001'
config = json.loads(Path('governance/state/report_period_config.json').read_text(encoding='utf-8'))
assert config['owner'] == 'OPERATOR'
assert config['default_period'] == '1h'
print('BEM-939 Block H Telegram validator PASS')
