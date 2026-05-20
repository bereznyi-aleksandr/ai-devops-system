# BEM-702 | Mandatory ChatGPT Task Monitor Rule

Дата: 2026-05-20 | 22:21 (UTC+3)
Версия: v1.0-2026-05-20
Статус: ACTIVE_RULE

## Правило
Каждый раз, когда GPT отправляет запрос Claude / внутреннему аудиту через mailbox, GPT обязан в том же операторском цикле создать или обновить ChatGPT Scheduled Task для проверки ответа.

## Обязательный task prompt
Создай или обнови повторяющуюся задачу `AI DevOps Claude mailbox monitor`. Расписание: каждые 1 минуту; если 1 минута недоступна — минимальный доступный повторяющийся интервал. Задача проверяет active agreements и Claude mailbox, фиксирует APPROVED / CHANGE_REQUIRED / BLOCKED через Codex task, не запускает roadmap implementation без команды resume, No issue comments.

## Evidence rule
PASS допускается только если есть task-card / task confirmation / repo record. Если task-card не появился, статус: TASK_SCHEDULER_CONFIRMATION_MISSING, а не PASS.

## Scope
Это эксплуатационное правило связи с Claude. Оно не является продолжением paused roadmap implementation.

## BEM-705 | Correction and fallback
Дата: 2026-05-20 | 22:41 (UTC+3)

After each Claude mailbox request, GPT must create/update ChatGPT Task from chat and require task-card confirmation. If confirmation is missing, status is BLOCKER, not PASS. Repo-side fallback is allowed only as alert layer through the already-permitted `curator-hourly-report.yml` schedule; it does not replace ChatGPT Task autonomy.
