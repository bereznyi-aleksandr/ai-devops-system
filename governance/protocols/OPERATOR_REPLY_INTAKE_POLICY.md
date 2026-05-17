# BEM-585 | Operator Reply Intake Policy

Дата: 2026-05-17 | 22:24 (UTC+3)

## Проблема

Оператор может получить decision message и ответить `1`, но без отдельного intake-канала этот ответ не попадёт в repo. Ошибка HTTP 403 означает, что текущий входящий путь Telegram не имеет прав или ведёт не в тот обработчик.

## Правило

1. Telegram отправка решения и приём ответа — разные контуры.
2. Ответ оператора `1/2/3/свой вариант` должен фиксироваться в `governance/operator_decisions/<decision_id>.json`.
3. После фиксации решения создаётся handoff куратору.
4. Если webhook недоступен, нужен fallback: GitHub Action poller через Telegram Bot API `getUpdates`.

## Требуемый контур

Telegram message -> operator reply -> intake handler/poller -> operator_decisions JSON -> curator handoff.
