# BEM-568 | Fix Smoke Python Without Compile | PASS

Дата: 2026-05-17 | 21:05 (UTC+3)

## Result
`scripts/claude_token_smoke.py` rewritten using safe source_lines generation. Removed unsupported `compile()` call.

## Security
Token value is never printed.

## Blocker
null
