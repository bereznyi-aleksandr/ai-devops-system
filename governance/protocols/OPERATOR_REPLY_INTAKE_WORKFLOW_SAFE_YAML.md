# BEM-591 | Operator Reply Intake Workflow Safe YAML

Дата: 2026-05-17 | 22:40 (UTC+3)

## Ошибка

`operator-reply-intake.yml` ломался на inline Python heredoc внутри YAML run block.

## Решение

Workflow больше не содержит heredoc/inline Python. Он только вызывает Telegram `getUpdates`, сохраняет JSON и передаёт его в `scripts/operator_reply_intake.py`.

## Результат

YAML должен проходить GitHub Actions validation. Парсинг и offset/seen логика остаются в Python parser.
