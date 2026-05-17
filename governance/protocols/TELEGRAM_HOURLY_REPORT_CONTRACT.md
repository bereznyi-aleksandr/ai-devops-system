# BEM-535.5 | Telegram Hourly Canonical Report Contract

Дата: 2026-05-17 | 13:15 (UTC+3)

## Реальный механизм
Custom GPT не запускается сам по расписанию. GitHub Actions `schedule` запрещён.

Разрешённый механизм hourly delivery:
`external cron service -> Deno endpoint -> workflow_dispatch curator-hourly-report.yml -> Telegram bot send`

## Требования к Deno endpoint
- Endpoint принимает authorized ping от external cron.
- Endpoint не хранит Telegram token в файлах.
- Endpoint запускает GitHub Actions через workflow_dispatch.
- Endpoint пишет trace/result в governance transport/state.

## Требования к workflow
- Только `workflow_dispatch`.
- No `schedule:` trigger.
- Генерирует canonical report payload.
- Отправляет через Telegram secret из runtime secrets, не из файла.

## Канонический отчёт
Должен содержать:
- BEM id / roadmap status.
- current contour status.
- provider state: Claude primary, GPT reserve, last switch.
- Telegram status.
- blocker.
- next action.
- timestamp UTC+3.

## Payload schema
```json
{
  "record_type": "telegram_hourly_report",
  "delivery_mode": "external_cron_to_deno_to_workflow_dispatch",
  "periodicity": "1h",
  "canonical": true,
  "message": "string",
  "blocker": null
}
```
