# BEM-548.5b | Live Regression Telegram | PASS WITH STALE QUEUE FIX

Дата: 2026-05-17 | 15:06 (UTC+3)

## Итог
Оператор показал live Telegram delivery: сообщение реально пришло в Telegram. Одновременно выявлен дефект очереди: ушло старое BEM-540 сообщение.

## Исправление
`telegram_outbox_pick.py` теперь выбирает newest high-priority current BEM-548 queued/ready message, чтобы старые synthetic сообщения не уходили первыми.

## Проверка
| Наименование | Описание | Обоснование |
|---|---|---|
| live delivery | observed by operator screenshot | Telegram chat shows delivered report |
| stale queue | fixed | picker priority policy updated |
| current message | queued as ready_to_send | `governance/telegram_outbox.jsonl` |
| repo sent records | 0 | transport scan |

## Blocker
null
