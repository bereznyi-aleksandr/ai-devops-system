# BEM-546 | Live Telegram Delivery Verification | WIRING_BLOCKER

Дата: 2026-05-17 | 14:41 (UTC+3)

## Проверка
| Наименование | Описание | Обоснование |
|---|---|---|
| Repo wiring | False | Workflow checks below |
| Live sent records | 0 | `telegram_delivery_result.status=sent` in transport |
| Delivery records total | 4 | transport scan |
| Verification message | queued | `governance/telegram_outbox.jsonl` |

## Workflow checks
```json
{
  "curator_hourly_exists": true,
  "curator_hourly_schedule": true,
  "curator_hourly_cron_hourly": true,
  "curator_hourly_uses_token_secret": true,
  "curator_hourly_uses_chat_secret": true,
  "curator_hourly_calls_picker": true,
  "curator_hourly_calls_recorder": true,
  "curator_hourly_no_issue_31": false,
  "standalone_sender_exists": true,
  "standalone_sender_dispatch": true,
  "standalone_sender_uses_token_secret": true,
  "standalone_sender_uses_chat_secret": true
}
```

## Diagnosis
Sender is wired, but no live `sent` record exists yet. The next `curator-hourly-report.yml` run should consume the queued verification message and write delivery_result.

## Blocker
{"code": "TELEGRAM_WIRING_INCOMPLETE", "checks": {"curator_hourly_exists": true, "curator_hourly_schedule": true, "curator_hourly_cron_hourly": true, "curator_hourly_uses_token_secret": true, "curator_hourly_uses_chat_secret": true, "curator_hourly_calls_picker": true, "curator_hourly_calls_recorder": true, "curator_hourly_no_issue_31": false, "standalone_sender_exists": true, "standalone_sender_dispatch": true, "standalone_sender_uses_token_secret": true, "standalone_sender_uses_chat_secret": true}}
