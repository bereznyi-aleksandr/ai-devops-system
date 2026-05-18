# BEM-602 | Telegram Reply Intake Hardening

Дата: 2026-05-18 | 05:56 (UTC+3)

## Цель

Убрать зависимость от chat fallback для ответа оператора `1/2/3` и сделать intake диагностируемым.

## Что усиливается
1. `getWebhookInfo` перед `getUpdates`: если webhook активен, poller честно фиксирует конфликт.
2. HTTP 403 классифицируется как `TELEGRAM_FORBIDDEN` с понятным blocker.
3. Parser сохраняет status даже если updates пустые или API вернул ошибку.
4. Commit result всегда сохраняет evidence: webhook_info, http_status, parse status.

## Правило
Если active webhook есть, polling через getUpdates может не работать. Тогда inbound intake должен идти через webhook endpoint, а poller остаётся диагностикой/fallback.
