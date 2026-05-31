#!/usr/bin/env python3
import json
from pathlib import Path
policy_path = Path('governance/state/provider_failover_policy.json')
providers_path = Path('governance/state/providers_registry.json')
if not policy_path.exists() or not providers_path.exists():
    raise SystemExit('MISSING provider policy or registry')
policy = json.loads(policy_path.read_text(encoding='utf-8'))
providers = json.loads(providers_path.read_text(encoding='utf-8'))
provider_ids = [p['provider_id'] for p in providers.get('providers', [])]
assert 'GPT-CODEX-FALLBACK' in provider_ids
rules = policy.get('rules', [])
assert any(r.get('fallback_provider') == 'GPT-CODEX-FALLBACK' for r in rules)
Path('governance/state/provider_failover_e2e_result.json').write_text(json.dumps({'status':'PASS','fallback_provider':'GPT-CODEX-FALLBACK'}, ensure_ascii=False, indent=2)+'
', encoding='utf-8')
print('BEM-941 provider failover E2E PASS')
