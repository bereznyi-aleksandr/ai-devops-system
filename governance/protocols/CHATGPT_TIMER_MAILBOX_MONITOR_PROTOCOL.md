# BEM-700 | ChatGPT Timer Mailbox Monitor Protocol

Дата: 2026-05-20 | 20:45 (UTC+3)
Версия: v1.0-2026-05-20
Статус: DRAFT_FOR_OPERATOR_SETUP

## Цель
Создать GPT-side механизм периодического пробуждения через ChatGPT Tasks, чтобы GPT сам проверял mailbox/active agreements и не ждал пересказа оператора.

## Архитектурное решение
Основной механизм: ChatGPT Scheduled Task в этом GPT/чате.
Fallback: repo-side watcher + Telegram operator notification.

## Smoke-test
Перед постоянным таймером создать одноразовую задачу на ближайшие 2 минуты. Задача должна выполнить Deno healthCheck и проверить active agreements. Если task context не имеет доступа к Deno tools, таймер считается неполным и остается только как notification layer.

## Production schedule
Желаемый режим: каждую 1 минуту. Если UI/OpenAI ограничит частоту, использовать минимально разрешенный интервал и repo-side event watcher.

## Acceptance criteria
1. Task запускается без оператора.
2. Task читает repo state/mailbox через Deno/Codex или фиксирует blocker, если tools недоступны.
3. При ответе Claude task переводит active agreement в следующий шаг без пересказа оператором.
4. Если требуется оператор — отправляется краткий Telegram/ChatGPT notification, содержание берется из repo.
