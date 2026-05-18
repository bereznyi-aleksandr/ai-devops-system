# BEM-669 | Operator Telegram Report Canon

Дата: 2026-05-18 | 16:08 (UTC+3)

## Hourly monitoring report
Keep only: title, date/time, stage percent, roadmap percent, and one readable table with columns `№`, `Наименование`, `Краткая суть`, `Статус`.

Do not show raw trace IDs as operator-facing events. Do not include long monitoring bullet lists.

Schedule: only `curator-hourly-report.yml` may use cron, exactly `0 * * * *`. The rendered report shows the report hour as `HH:00 (UTC+3)`.

## Approval message
Header contains short question and date/time. Table columns: `№`, `Наименование варианта`, `Обоснование`. Operator answers with option number or custom text.
