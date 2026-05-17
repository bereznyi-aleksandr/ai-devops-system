# BEM-549 | Operator Progress Feed

Дата: 2026-05-17 | 15:12 (UTC+3)

## Проблема
Мобильный ChatGPT показывает экран агента/отслеживания во время tool/action. Агент не может отключить UI клиента.

## Решение
Ход разработки выводится не только в чат, но и в стабильный внешний feed:

| Канал | Файл | Назначение |
|---|---|---|
| repo jsonl | `governance/state/operator_progress_feed.jsonl` | append-only события прогресса |
| repo current | `governance/state/operator_progress_current.json` | последняя задача/этап/статус |
| Telegram outbox | `governance/telegram_outbox.jsonl` | короткие сообщения статуса |

## Правило
1. В ChatGPT: минимум сообщений.
2. В repo/Telegram: видимый прогресс по каждому этапу.
3. Отчёт в ChatGPT только после закрытия этапа/blocker.
4. Если ChatGPT UI показывает экран агента, оператор смотрит Telegram/progress files.
