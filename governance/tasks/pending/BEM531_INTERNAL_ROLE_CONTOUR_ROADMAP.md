# BEM-531 | Internal Role Contour Improvement Roadmap

Дата: 2026-05-17 | 12:35 (UTC+3)

## Объект
Внутренний контур разработки: external inputs GPT/Claude/Telegram -> curator -> analyst -> auditor -> executor -> GitHub Actions -> file transport -> role state. Это не внешний GPT autonomy contour.

## Цель
Довести внутренний мультиагентный контур до проверяемого E2E состояния, где curator принимает/маршрутизирует вход, роли создают артефакты, передают их через файловый транспорт, executor применяет изменения, auditor подтверждает, state обновляется.

## Дорожная карта доработок

### BEM-531.00 — Repository archive cleanup preflight
Цель: перед доработкой внутреннего контура провести полный аудит репозитория и заархивировать файлы/записи, которые не являются активной частью внешнего или внутреннего контура.

Задачи:
- построить inventory активных файлов: workflows, state, transport, protocols, reports, tasks;
- определить устаревшие failed/superseded artifacts, stale pending tasks, legacy proofs/results и исторические blocker-файлы;
- переносить мусор только в governance/archive с manifest, без безвозвратного удаления;
- не нарушить внешний GPT autonomy contour: Deno, codex-runner, Python executor v3, reports/results;
- не нарушить внутренний role-based contour: curator, analyst, auditor, executor, role state, transport, orchestrator, provider-adapter;
- создать cleanup report для Claude/GPT с перечнем archived/kept файлов и обоснованием.

PASS:
- archive manifest exists;
- cleanup report exists;
- active workflows/state/transport remain valid;
- no issue #31 comments;
- no schedule triggers;
- no paid API;
- blocker=null.


### BEM-531.01 — Unified curator intake architecture
Цель: зафиксировать единую точку входа внутреннего контура: GPT external auditor, Claude external auditor и Telegram bot/webhook входят через curator. Curator делает intake, triage, normalizes request, пишет role_cycle_state и направляет в analyst/auditor/executor.
PASS: architecture report, curator intake schema, transport sample for all three external branches.


### BEM-531.0 — Curator role contract
Цель: формализовать роль curator как входной диспетчер внутреннего контура: intake, triage, назначение analyst/auditor/executor, контроль handoff и закрытие цикла.
PASS: curator fields added to role_cycle_state schema, transport contract and synthetic E2E.


### BEM-531.1 — Role state schema audit and normalization
Проверить и нормализовать governance/state/role_cycle_state.json: active_role, cycle_id, current_task, handoff pointers, status history, blocker, timestamps.
PASS: schema report, normalized state, backward-compatible fields.

### BEM-531.2 — File transport contract
Формализовать inbox/outbox/result файлы для ролей и стандартизировать JSONL schema.
PASS: transport protocol + sample records + validator proof.

### BEM-531.3 — Role orchestrator workflow audit
Проверить role-orchestrator.yml: triggers, inputs, state read/write, no schedule, no issue #31, routing curator/analyst/auditor/executor.
PASS: audit report + patch if required.

### BEM-531.4 — Provider adapter workflow audit
Проверить provider-adapter.yml: provider routing, file transport write, failure handling, no paid API by default, no secrets leakage.
PASS: audit report + patch if required.

### BEM-531.5 — Synthetic role cycle E2E
Создать тестовую задачу: curator intake -> analyst analysis -> auditor review -> executor file patch -> auditor final PASS -> curator closure -> transport result.
PASS: all role artifacts exist, role_cycle_state updated, result record appended, blocker=null.

### BEM-531.6 — Internal contour dashboard
Создать governance/internal_contour/status.md: роли, последний cycle, last result, blockers, next role.
PASS: dashboard generated from state/transport files.

## Приоритет
1. BEM-531.00 repository archive cleanup preflight.
2. BEM-531.01 curator intake architecture.
3. BEM-531.1 state schema.
4. BEM-531.2 file transport contract.
5. BEM-531.3/531.4 workflows.
6. BEM-531.5 synthetic E2E.
7. BEM-531.6 dashboard.

## Ограничения
No issue #31 comments. No schedule triggers. No secrets in files. No paid OpenAI API. Use Deno + Python executor v3 Run script.

## Количество этапов
Roadmap BEM-531 состоит из 8 этапов: BEM-531.00 cleanup, BEM-531.01 curator intake, BEM-531.1 state schema, BEM-531.2 transport, BEM-531.3 orchestrator, BEM-531.4 provider adapter, BEM-531.5 synthetic E2E, BEM-531.6 dashboard.
