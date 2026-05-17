# BEM-535.5 | Telegram Hourly Canonical Report Contract

Дата: 2026-05-17 | 13:15 (UTC+3)

## Реальный механизм
Contract v1.9 allows one schedule exception: `.github/workflows/curator-hourly-report.yml` with cron `0 * * * *`. Other GitHub Actions schedule triggers remain prohibited.

Разрешённый механизм hourly delivery:
`GitHub Actions schedule cron `0 * * * *` -> curator-hourly-report.yml -> governance/telegram_outbox.jsonl -> Deno or separate sender delivers to Telegram`

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


## BEM-535 Claude correction
BEM-535.5 is considered DONE by external auditor Claude after curator-hourly-report.yml restored hourly cron and continue-on-error safeguards. This workflow must not write issue #31 and must not create email storm.
