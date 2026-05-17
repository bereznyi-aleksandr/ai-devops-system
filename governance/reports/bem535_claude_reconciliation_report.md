# BEM-535 | Claude Reconciliation Report | PARTIAL

Дата: 2026-05-17 | 13:31 (UTC+3)

## Что произошло
Claude обновил контракт до v1.9 и восстановил schedule только для `.github/workflows/curator-hourly-report.yml`. Это исключение принято и отражено в state/protocol files.

## Проверки
```json
{
  ".github/workflows/curator-hourly-report.yml": {
    "exists": true,
    "workflow_dispatch": true,
    "schedule": true,
    "cron_hourly": true,
    "continue_on_error": true,
    "issue_31": true,
    "transport_results": false,
    "telegram_outbox": true,
    "failed_or_cancelled": false
  },
  ".github/workflows/provider-adapter.yml": {
    "exists": true,
    "workflow_dispatch": true,
    "schedule": false,
    "cron_hourly": false,
    "continue_on_error": false,
    "issue_31": false,
    "transport_results": true,
    "telegram_outbox": false,
    "failed_or_cancelled": true
  },
  ".github/workflows/claude.yml": {
    "exists": true,
    "workflow_dispatch": true,
    "schedule": false,
    "cron_hourly": false,
    "continue_on_error": true,
    "issue_31": true,
    "transport_results": true,
    "telegram_outbox": false,
    "failed_or_cancelled": true
  }
}
```

## Решения, зафиксированные после аудита Claude
| Наименование | Описание | Обоснование |
|---|---|---|
| Schedule exception | Разрешён только `curator-hourly-report.yml` с cron `0 * * * *` | Claude: причина BEM-476 устранена, workflow не пишет issue #31 и имеет continue-on-error |
| Claude limit detection | Использовать `claude.yml outcome=failure/cancelled` или transport `status=failed/cancelled/timeout` | У Claude нет API самосообщения UI-лимитов |
| Provider failover | Claude failed/cancelled/timeout -> GPT reserve | Реализовано в provider-adapter policy |
| Telegram hourly path | `curator-hourly-report.yml -> governance/telegram_outbox.jsonl -> Deno/sender -> Telegram` | Это текущая разрешённая архитектура v1.9 |

## Status
PARTIAL

## Blocker
Нужно ручное review workflow checks выше
