# BEM-576 | Telegram Inline Operator Decision Buttons

Дата: 2026-05-17 | 21:48 (UTC+3)

## Ответ

Да, можно сделать выбор варианта через кнопки/галочки в Telegram.

## Правильная реализация

Telegram должен отправлять operator decision message с inline-кнопками:

1. ✅ 1 Подтвердить
2. ↩️ 2 На доработку
3. ✍️ 3 Свой вариант

После нажатия Telegram отправляет callback_query боту. Чтобы выбор реально зафиксировался, нужен callback-handler.

## Почему нельзя ограничиться только кнопками

| Наименование | Описание | Обоснование |
|---|---|---|
| Кнопки | Можно показать в Telegram-сообщении | Telegram Bot API поддерживает inline_keyboard |
| Фиксация выбора | Нужен callback-handler | Без него кнопка нажмётся, но решение не попадёт в repo |
| Запись решения | `governance/operator_decisions/<decision_id>.json` | Куратор должен получить machine-readable decision |
| Fallback | Текстовый ответ `1 / 2 / 3 / свой вариант` остаётся | Если callback сломался, оператор всё равно может ответить |

## Цепочка

Telegram кнопка -> callback-handler -> repo decision record -> Curator -> Role-orchestrator -> internal contour.

## Callback data

- `decision:<decision_id>:1`
- `decision:<decision_id>:2`
- `decision:<decision_id>:3`

## Следующая реализация

| Этап | Что сделать | PASS |
|---|---|---|
| BEM-576.1 | Добавить inline_keyboard в operator decision sender | В Telegram видны кнопки |
| BEM-576.2 | Добавить callback-handler | Нажатие кнопки пишет decision JSON |
| BEM-576.3 | Передать decision куратору | Curator принимает решение в работу |
| BEM-576.4 | Live test | Оператор нажал кнопку, repo получил decision |
