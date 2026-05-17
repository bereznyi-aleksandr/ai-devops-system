# BEM-552 | Telegram Hourly Scheduler Fix | PASS

Дата: 2026-05-17 | 16:05 (UTC+3)

## Diagnosis
Оператор не получил hourly Telegram report через час. Scheduler path был переписан в минимальный надёжный workflow: generate -> pick -> send -> record -> commit.

## Checks
```json
{
  "workflow_exists": true,
  "has_schedule": true,
  "has_cron": true,
  "has_dispatch": true,
  "uses_token": true,
  "uses_chat": true,
  "calls_generator": true,
  "calls_picker": true,
  "calls_recorder": true,
  "no_issue31": true
}
```

## Limitation
GitHub schedule может выполняться с задержкой и не запускается мгновенно. Для немедленной проверки нужен workflow_dispatch или ближайший cron.

## Blocker
null
