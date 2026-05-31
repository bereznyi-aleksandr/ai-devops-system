#!/usr/bin/env python3
import json
from pathlib import Path
required = [
  'governance/audit/claude_reaudit_checklist.json',
  'governance/audit/evidence_index.json',
  'governance/audit/audit_bundle_manifest.json'
]
missing = [p for p in required if not Path(p).exists()]
if missing:
    raise SystemExit('MISSING: ' + ', '.join(missing))
manifest = json.loads(Path('governance/audit/audit_bundle_manifest.json').read_text(encoding='utf-8'))
missing_includes = [p for p in manifest['include'] if not Path(p).exists()]
if missing_includes:
    raise SystemExit('MISSING_BUNDLE_INCLUDE: ' + ', '.join(missing_includes))
print('BEM-943 Block L audit validator PASS')
