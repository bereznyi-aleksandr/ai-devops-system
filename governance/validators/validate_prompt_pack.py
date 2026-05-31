#!/usr/bin/env python3
from pathlib import Path
required = [
  'governance/prompts/templates/curator_template.md',
  'governance/prompts/templates/analyst_template.md',
  'governance/prompts/templates/auditor_template.md',
  'governance/prompts/templates/executor_template.md',
  'governance/prompts/providers/gpt_analyst_provider.md',
  'governance/prompts/providers/claude_auditor_provider.md',
  'governance/prompts/providers/claude_executor_provider.md',
  'governance/prompts/providers/codex_fallback_provider.md',
  'governance/prompts/handlers/telegram_input_handler.md',
  'governance/prompts/handlers/dispatch_consumer.md',
  'governance/prompts/handlers/managed_channel_consumer.md'
]
missing = [p for p in required if not Path(p).exists()]
if missing:
    raise SystemExit('MISSING: ' + ', '.join(missing))
for p in required:
    text = Path(p).read_text(encoding='utf-8')
    if 'промпт объекта' in text.lower():
        raise SystemExit('INVALID object prompt wording in ' + p)
print('BEM-934 prompt pack validator PASS')
