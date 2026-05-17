# BEM-550.2 | Telegram Progress Queue Policy

Дата: 2026-05-17 | 15:17 (UTC+3)

## Проблема
Live Telegram sender отправил stale BEM-540 сообщение раньше текущего BEM-548 статуса.

## Политика очереди
| Правило | Описание |
|---|---|
| current first | BEM текущей дорожной карты имеет максимальный приоритет |
| stale guard | Старые synthetic/system-test сообщения не уходят в live, если есть current ready message |
| dedupe | Уже доставленные outbox_line/message_hash не повторяются |
| operator progress | Progress-сообщения имеют приоритет над hourly summary |
| single pick | Sender выбирает одну самую приоритетную запись за запуск |
