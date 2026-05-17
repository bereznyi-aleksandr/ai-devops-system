# BEM-568 | Auto-run Claude Token Smoke | PASS

Дата: 2026-05-17 | 21:00 (UTC+3)

## Result
`claude-token-smoke.yml` now has `workflow_dispatch` and safe `push` trigger limited to the smoke workflow/script paths. This lets GitHub run the smoke automatically after this commit without operator manual Run workflow.

## Security
The smoke only checks whether the secret exists. It never prints token value.

## Blocker
null
