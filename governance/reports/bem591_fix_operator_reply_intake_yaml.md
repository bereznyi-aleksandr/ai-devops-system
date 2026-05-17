# BEM-591 | Fix Operator Reply Intake YAML | PASS

Дата: 2026-05-17 | 22:40 (UTC+3)

Removed inline Python heredoc from `operator-reply-intake.yml`. Workflow now fetches Telegram updates with curl only and delegates parsing to `scripts/operator_reply_intake.py`.

Blocker: null
