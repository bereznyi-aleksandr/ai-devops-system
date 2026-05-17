# BEM-589 | Operator Decision Chat Fallback

Дата: 2026-05-17 | 22:34 (UTC+3)

## Правило

Если Telegram intake временно не зафиксировал ответ, но оператор явно дал ответ в текущем чате/скриншоте, GPT может создать decision record с источником `chat_fallback_after_telegram_403`.

## Условие
Такой fallback допустим только если ответ оператора однозначен: `1`, `2`, `3`, `да`, `подтверждаю` или текстовое решение.

## Результат
Создаётся `governance/operator_decisions/<decision_id>.json` и handoff куратору.
