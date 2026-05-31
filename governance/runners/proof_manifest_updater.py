#!/usr/bin/env python3
from pathlib import Path
import json
from datetime import datetime, timezone

MANIFEST = Path('governance/state/release_proof_manifest.json')


def load_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding='utf-8'))
    return {'version': '1.0', 'release_status': 'draft', 'commit_sha': None, 'actions_run_id': None, 'validation_statuses': {}, 'proof_refs': [], 'blockers': []}


def add_proof(block_id, status, proof_ref):
    m = load_manifest()
    m['date'] = datetime.now(timezone.utc).date().isoformat()
    m.setdefault('validation_statuses', {})[block_id] = status
    m.setdefault('proof_refs', [])
    if proof_ref not in m['proof_refs']:
        m['proof_refs'].append(proof_ref)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=2) + '
', encoding='utf-8')
    return m

if __name__ == '__main__':
    print(json.dumps(add_proof('proof_manifest_updater_selftest','PASS','governance/state/release_proof_manifest.json'), ensure_ascii=False))
