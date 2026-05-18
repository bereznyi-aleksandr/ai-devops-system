# BEM-605 | Analyst Plan | Hourly Telegram Report Canon

Дата: 2026-05-18 | 06:06 (UTC+3)

## Problem
Hourly Telegram report is not canonical and does not explain route/provider/checks. Operator cannot evaluate system health from it.

## Proposed template
BEM-HOURLY | SYSTEM MONITORING REPORT | YYYY-MM-DD | HH:MM (UTC+3)

Этап: X/Y (Z%)
Дорожная карта: X/Y (Z%)

Чек-лист:
✅ Роли/контуры проверены
✅ Provider gate выполнен
✅ Последние события собраны
⚠️ Blocker если есть

Таблица:
Наименование | Описание | Обоснование

Rows: Текущий этап, Последнее действие, Provider route, Основной контур, Резервный контур, Telegram delivery, Blocker, Следующее действие.

## Claude questions

- Подтверждаешь ли этот канон hourly report?
- Нужно ли разделить hourly status и operator decision request?
- Какие поля обязательны для provider route: provider_checked, selected_provider, reserve_used, reason, proof_file?
- Какой минимальный формат будет читабельным в Telegram на телефоне?

## Blocker
null
