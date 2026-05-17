# BEM-568 | Fix Claude Token Smoke YAML | PASS

Дата: 2026-05-17 | 20:58 (UTC+3)

## Result
Invalid inline here-doc workflow replaced by valid workflow that calls `scripts/claude_token_smoke.py`.

## Security
Token value is never printed; only secret_present/secret_missing status is printed.

## Blocker
null
