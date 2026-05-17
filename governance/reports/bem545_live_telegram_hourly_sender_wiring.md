# BEM-545 | Live Telegram Hourly Sender Wiring | BLOCKER

Дата: 2026-05-17 | 14:38 (UTC+3)

## Исправление
Оператор показал, что `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID` уже существуют в GitHub Secrets. Добавлять их заново не нужно.

## Что сделано
- Live sender подключён к разрешённому `.github/workflows/curator-hourly-report.yml`.
- Workflow использует runtime secrets `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID`.
- Sender пишет `telegram_delivery_result` в `governance/transport/results.jsonl`.

## Checks
```json
{
  "curator_hourly_exists": true,
  "sender_workflow_exists": true,
  "hourly_has_schedule": true,
  "hourly_has_cron": true,
  "hourly_has_continue_on_error": true,
  "hourly_uses_token_secret": true,
  "hourly_uses_chat_secret": true,
  "hourly_calls_picker": true,
  "hourly_calls_recorder": true,
  "no_issue_31": false
}
```

## Что остаётся
Live PASS появится после ближайшего запуска `curator-hourly-report.yml` или ручного `workflow_dispatch`: в transport должна появиться запись `telegram_delivery_result.status=sent`.

## Blocker
{"code": "TELEGRAM_HOURLY_WIRING_FAILED", "checks": {"curator_hourly_exists": true, "sender_workflow_exists": true, "hourly_has_schedule": true, "hourly_has_cron": true, "hourly_has_continue_on_error": true, "hourly_uses_token_secret": true, "hourly_uses_chat_secret": true, "hourly_calls_picker": true, "hourly_calls_recorder": true, "no_issue_31": false}}
