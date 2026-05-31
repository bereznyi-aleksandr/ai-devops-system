#!/usr/bin/env python3
import json
from pathlib import Path
manifest_path = Path('governance/state/release_proof_manifest.json')
schema_path = Path('governance/state/schemas/release_proof_manifest_schema.json')
if not manifest_path.exists():
    raise SystemExit('MISSING: release_proof_manifest.json')
if not schema_path.exists():
    raise SystemExit('MISSING: release_proof_manifest_schema.json')
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
schema = json.loads(schema_path.read_text(encoding='utf-8'))
missing = [k for k in schema['required_fields'] if k not in manifest]
if missing:
    raise SystemExit('MISSING_FIELDS: ' + ', '.join(missing))
if manifest.get('release_status') == 'release_pass' and not manifest.get('commit_sha'):
    raise SystemExit('RELEASE_PASS_FORBIDDEN_WITH_NULL_SHA')
for proof in manifest.get('proof_refs', []):
    if not Path(proof).exists():
        raise SystemExit('MISSING_PROOF_REF: ' + proof)
print('BEM-940 release proof validator PASS')
