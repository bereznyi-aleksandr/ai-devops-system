# BEM-530 | Internal Contour Improvement Roadmap

Дата: 2026-05-17 | 12:28 (UTC+3)

## Цель
Доработать внутренний контур разработки после закрытия базовой автономности.

## Исходное состояние
- Roadmap P0-P11: закрыт.
- Current phase: COMPLETE
- Executor: ubuntu-latest Python executor v3.
- Paid API: disabled.
- Codex CLI: disabled.
- Write channel: Deno createCodexTask.

## Roadmap доработок

### BEM-530.1 — Executor v3 hardening
Цель: формализовать и протестировать Run script sandbox.
Задачи: allowed globals, script templates, negative tests for blocked capabilities, better result fields.
PASS: report + proof + negative-test results.

### BEM-530.2 — Role Cycle E2E business scenario
Цель: проверить analyst/auditor/executor цикл на реалистичной задаче.
Задачи: synthetic request, analyst output, auditor review, executor patch, state update, report.
PASS: role artifacts exist, state updated, blocker=null.

### BEM-530.3 — Transport observability
Цель: сделать результаты контура читаемыми без ручного поиска.
Задачи: result schema, transport index, latest tasks, status, SHA, blocker, health snapshot.
PASS: transport index and health snapshot created.

### BEM-530.4 — Recovery automation pack
Цель: сократить ручной recovery при сбоях.
Задачи: queued/failed/not_found scenarios, recovery templates, self-tests.
PASS: runbook + template proofs.

### BEM-530.5 — Documentation sync
Цель: синхронизировать GPT_HANDOFF, GPT_WRITE_CHANNEL, INTERNAL_CONTOUR_REFERENCE с фактической архитектурой.
Задачи: remove outdated paid API path, describe free executor policy, chained-roadmap mode, operator-facing report rule.
PASS: docs updated + audit proof.

## Приоритет
1. BEM-530.1 Executor v3 hardening.
2. BEM-530.2 Role Cycle E2E business scenario.
3. BEM-530.3 Transport observability.
4. BEM-530.4 Recovery automation pack.
5. BEM-530.5 Documentation sync.

## Ограничения
- No issue #31 comments.
- No schedule triggers.
- No secrets in files.
- No paid OpenAI API.
- Codex CLI disabled unless separately approved.
