# BEM-840 | CLAUDE TOKEN ROTATION INSTRUCTION

Дата: 2026-05-22 | 06:02 (UTC+3)

Добавлена инструкция: `governance/runbooks/CLAUDE_CODE_TOKEN_ROTATION.md`.

Ключевые правила:
- token получает только оператор локально через `claude setup-token`;
- token добавляется только в GitHub Actions Secret `CLAUDE_CODE_OAUTH_TOKEN`;
- token не передаётся агенту и не записывается в репозиторий;
- после обновления секрета агент обязан выполнить smoke-loop;
- PASS разрешён только при наличии dispatch result, Claude runtime state и real Claude response.

No issue comments.
