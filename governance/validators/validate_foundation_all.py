#!/usr/bin/env python3
from pathlib import Path
import json

required_files = [
  'governance/state/protocol_quality_rules.json',
  'governance/state/roadmap_dependencies.json',
  'governance/state/object_passports.json',
  'governance/state/contours_registry.json',
  'governance/state/providers_registry.json',
  'governance/state/contour_provider_policy.json',
  'governance/state/provider_failover_policy.json',
  'governance/prompts/templates/curator_template.md',
  'governance/prompts/templates/analyst_template.md',
  'governance/prompts/templates/auditor_template.md',
  'governance/prompts/templates/executor_template.md',
  'governance/state/managed_channel_schema.json',
  'governance/state/contour_lifecycle_schema.json',
  'governance/state/event_log_schema.json',
  'governance/runners/managed_channel_consumer.py',
  'governance/runners/dispatch_consumer.py',
  'governance/runners/contour_lifecycle_runner.py',
  'governance/state/telegram_input_envelope_schema.json',
  'governance/state/telegram_to_managed_channel_mapping.json',
  'governance/state/report_period_config.json',
  'governance/state/release_proof_manifest.json',
  'governance/state/telegram_e2e_status.json',
  'governance/gates/production_operator_gate.json',
  'governance/audit/claude_reaudit_checklist.json',
  'governance/audit/evidence_index.json'
]
missing = [p for p in required_files if not Path(p).exists()]
if missing:
    raise SystemExit('MISSING_FOUNDATION_FILES: ' + ', '.join(missing))

# JSON parse check for state/audit/gates json files
for p in required_files:
    if p.endswith('.json'):
        json.loads(Path(p).read_text(encoding='utf-8'))

manifest = json.loads(Path('governance/state/release_proof_manifest.json').read_text(encoding='utf-8'))
if manifest.get('release_status') == 'release_pass' and not manifest.get('commit_sha'):
    raise SystemExit('INVALID_RELEASE_PASS_WITH_NULL_SHA')

telegram = json.loads(Path('governance/state/telegram_e2e_status.json').read_text(encoding='utf-8'))
if telegram.get('production_status') == 'PASS':
    raise SystemExit('INVALID_PRODUCTION_PASS_WITHOUT_GATE')

print('BEM-944 foundation all validator PASS')
