# BEM-550.9 | Monitoring and Alerting

Дата: 2026-05-17 | 15:41 (UTC+3)

## Alerts
Send Telegram/file alert for invalid workflow, provider reserve switch, delivery failure, stale queue, blocker not null.

## Rule
Never issue #31. Alerts go to transport/results.jsonl and telegram_outbox.jsonl.
