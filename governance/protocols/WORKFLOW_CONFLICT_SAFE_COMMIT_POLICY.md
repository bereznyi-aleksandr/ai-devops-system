# BEM-606 | Workflow Conflict-Safe Commit Policy

Дата: 2026-05-18 | 06:13 (UTC+3)

## Проблема

Параллельные workflow пишут в `governance/transport/results.jsonl`. При `git pull --rebase` возникает конфликт на append-only файле, из-за чего GitHub Actions шлёт оператору ложные fail-уведомления.

## Решение

1. Автономные dispatcher/router workflow больше не коммитят общий `governance/transport/results.jsonl`.
2. Каждый workflow коммитит только свои state/report/inbox/task файлы.
3. Каноничный transport остаётся для Deno/Codex tasks, где коммит выполняется централизованно.
4. Для workflow-доказательств используются `governance/reports/*` и `governance/state/*`.

## Цель

Убрать конфликтный шум и не ломать roadmap при параллельных фоновых действиях.
