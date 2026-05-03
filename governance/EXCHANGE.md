# EXCHANGE.md — DEPRECATED
# Дата: 2026-05-03 | E3-CLEANUP Этап 0D

Этот файл больше не является рабочим state layer системы.

## Активный state layer (использовать вместо этого файла):

- `governance/state/routing.json` — текущая маршрутизация ролей
- `governance/state/system_state.json` — текущее состояние системы
- `governance/exchange.jsonl` — журнал событий (append-only)
- `governance/processed_events.jsonl` — защита от дублей
- `governance/telegram_outbox.jsonl` — исходящие сообщения оператору

## Правило:
Не писать операционное состояние в этот файл.
Не читать этот файл в workflows и prompts.
