# BEM-657 | Telegram Smoke Workflow No Heredoc

Дата: 2026-05-18 | 15:50 (UTC+3)

Telegram send smoke workflow must not use inline heredoc. Message is passed through a shell variable and curl `--data-urlencode`.
