# BEM-577 | Structured Operator Decision Queue

Дата: 2026-05-17 | 21:52 (UTC+3)

## Ошибка, которую исправляем

Нельзя формировать Telegram-запрос оператору из обычного mailbox-сообщения Claude/GPT.
Обычный audit response не содержит полноценного вопроса, сравнения вариантов и обоснований.

## Правило

Operator decision Telegram создаётся только из отдельного structured decision package в:

`governance/operator_decision_queue/<decision_id>.json`

Routine mailbox не отправляет Telegram.

## Обязательная структура decision package

- `decision_id`
- `bem`
- `title`
- `stage.done`, `stage.total`
- `roadmap.done`, `roadmap.total`
- `checklist[]`
- `question`
- `options[]`, где каждый option содержит:
  - `id`
  - `title`
  - `difference`
  - `rationale`
  - `impact`
- `recommendation.option_id`
- `recommendation.rationale`
- `reply_format`
- `handoff_to: curator`

## Telegram должен содержать

1. Каноничную шапку BEM.
2. Этап и дорожную карту с процентами.
3. Чек-лист.
4. Явный вопрос.
5. Вертикальную таблицу вариантов:
   - Вариант
   - Отличие
   - Обоснование
   - Последствие
6. Рекомендацию аудиторов.
7. Как ответить.

## Запрет

Если нет structured decision package, Telegram operator decision не отправлять.
