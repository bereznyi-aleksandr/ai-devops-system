# BEM-587 | Operator Reply Intake Autorun

Дата: 2026-05-17 | 22:30 (UTC+3)

## Решение

Operator Reply Intake больше не требует ручного запуска оператором.

## Механизм
1. `operator-reply-intake.yml` запускается вручную или через push-trigger по `governance/triggers/operator_reply_intake.trigger`.
2. Для немедленного запуска GPT делает marker commit в trigger file.
3. Для регулярного безопасного режима разрешено подключение к `curator-hourly-report.yml`, потому что это единственный разрешённый schedule workflow.

## Следующий слой
Добавить curator-hourly-report integration: hourly безопасно вызывает intake, фиксирует новые решения и передаёт куратору.
