#!/usr/bin/env python3
import json, os
from datetime import datetime, timedelta, timezone
from pathlib import Path
kyiv=timezone(timedelta(hours=3))
now=datetime.now(kyiv).strftime('%Y-%m-%d | %H:%M (UTC+3)')
Path('governance/state').mkdir(parents=True, exist_ok=True)
state={
  'schema_version':'claude_secret_wiring_check.v1',
  'checked_at':now,
  'ANTHROPIC_API_KEY_present':bool(os.environ.get('ANTHROPIC_API_KEY')),
  'CLAUDE_CODE_OAUTH_TOKEN_present':bool(os.environ.get('CLAUDE_CODE_OAUTH_TOKEN')),
  'note':'Only boolean presence is recorded. Secret values are never printed.'
}
if state['ANTHROPIC_API_KEY_present'] or state['CLAUDE_CODE_OAUTH_TOKEN_present']:
  state['status']='secret_present'
else:
  state['status']='secret_missing'
Path('governance/state/claude_secret_wiring_check.json').write_text(json.dumps(state, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
print(json.dumps({'status':state['status'],'ANTHROPIC_API_KEY_present':state['ANTHROPIC_API_KEY_present'],'CLAUDE_CODE_OAUTH_TOKEN_present':state['CLAUDE_CODE_OAUTH_TOKEN_present']}, ensure_ascii=False))
