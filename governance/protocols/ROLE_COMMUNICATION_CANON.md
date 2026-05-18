# BEM-625 | Role Communication Canon

Дата: 2026-05-18 | 07:24 (UTC+3)

## Правило 1 — внутренние роли НЕ общаются через audit_mailbox

Внутренний контур использует role-bus:
- `governance/curator/inbox/`
- `governance/role_orchestrator/inbox/`
- `governance/internal_contour/tasks/`
- `governance/internal_contour/analyst/plans/`
- `governance/internal_contour/auditor/inbox/`
- `governance/internal_contour/auditor/reports/`
- `governance/internal_contour/executor/inbox/`
- `governance/internal_contour/executor/reports/`

## Правило 2 — audit_mailbox только для аудиторов

`governance/audit_mailbox/` используется только для связи:
- внутренний аудитор ↔ внешний аудитор
- внешний аудитор ↔ внутренний аудитор

Аналитик не пишет внешнему аудитору напрямую через mailbox. Аналитик пишет внутреннему аудитору в `internal_contour/auditor/inbox/`.

## Правило 3 — роли и провайдеры различаются

Роль — Curator / Analyst / Internal Auditor / External Auditor / Executor.
Провайдер — GPT / Claude Code / GPT reserve / Codex direct write / Deno transport.

## Правило 4 — Deno

Deno является внешним транспортным адаптером текущего ChatGPT-агента к GitHub Actions. Он не является внутренним исполнителем и не должен подменять роль Executor в модели.
