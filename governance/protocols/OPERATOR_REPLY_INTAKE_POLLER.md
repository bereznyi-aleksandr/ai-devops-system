# BEM-586 | Operator Reply Intake Poller

Дата: 2026-05-17 | 22:27 (UTC+3)

## Назначение

Фиксировать текстовые ответы оператора `1`, `2`, `3` или свой вариант из Telegram в repo.

## Поток

1. GitHub Actions вызывает Telegram Bot API `getUpdates`.
2. Ответ сохраняется во временный JSON.
3. Python parser выбирает последнее сообщение от `TELEGRAM_CHAT_ID`.
4. Если текст похож на решение, создаётся `governance/operator_decisions/<decision_id>.json`.
5. Создаётся handoff-файл для куратора в `governance/tasks/pending/`.

## Ограничение

Без webhook или schedule poller запускается через `workflow_dispatch`. Для автоматического режима можно добавить вызов poller в безопасный существующий `curator-hourly-report.yml`, потому что только этот workflow имеет разрешённый schedule.
