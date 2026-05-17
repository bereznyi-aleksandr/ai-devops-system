# BEM-537 | Live Transport Orchestration Test Roadmap

Дата: 2026-05-17 | 13:36 (UTC+3)

## Цель
Проверить не только запись в `governance/transport/results.jsonl`, но и автоматическое чтение/реакцию transport-consumer logic внутри репозиторного контура.

## Граница теста
Реального отдельного workflow_dispatch для role-orchestrator/provider-adapter из GPT-канала сейчас нет. Поэтому BEM-537 проверяет live-like consumer внутри разрешённого Python executor v3: consumer читает append-only transport, выбирает next_role, пишет decision/state и result.

## Roadmap из 3 задач
1. Task 1 — создать transport consumer contract и synthetic input records.
2. Task 2 — выполнить consumer decision pass: прочитать transport, выбрать next_role/action, обновить state.
3. Task 3 — adapter reaction + final audit: проверить, что decision породил execution/final_result и закрыть roadmap.

## PASS
- consumer читает `results.jsonl`;
- consumer пишет decision artifact;
- state меняется на основании прочитанной записи;
- final transport result appended;
- blocker=null.
