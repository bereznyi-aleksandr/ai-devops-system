# BEM-573 | Mailbox Telegram Decision-only Policy

Дата: 2026-05-17 | 21:35 (UTC+3)

## Решение оператора

| Наименование | Описание | Обоснование |
|---|---|---|
| Routine mailbox | Не отправлять в Telegram | Оператор не должен получать шум и становиться relay |
| Claude↔GPT sync | Идёт через audit mailbox и GitHub Actions | Claude не читает Telegram; GPT читает mailbox |
| Telegram | Только для operator decision gate | Оператор подключается в момент согласования/финального решения |
| Strategic / disagreement | Отправлять оператору в Telegram | Только если требуется решение оператора |
| Recipient routing | Адресату сообщает mailbox/workflow, не Telegram | Telegram не является транспортом между Claude и GPT |

## Правило

Telegram используется только если файл mailbox явно содержит один из признаков:

- `Requires operator decision: yes`
- `Требует решения оператора: да`
- `OPERATOR DECISION REQUIRED`
- `operator_decision_required`
- `disagreement_requires_operator`
- `Архитектурное разногласие`

Обычные сообщения `Claude -> GPT` и `GPT -> Claude` не отправляются оператору.
