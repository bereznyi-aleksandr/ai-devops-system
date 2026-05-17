# BEM-538 | Runtime Workflow Dispatch Bridge Roadmap

Дата: 2026-05-17 | 13:41 (UTC+3)

## Цель
Довести проверку внутреннего контура от file-level synthetic consumer test до workflow-level runtime orchestration: dispatch `role-orchestrator.yml` and `provider-adapter.yml` с входами и проверкой transport/state результата.

## Исходная точка
BEM-537 доказал, что exchange file читается consumer-логикой и порождает adapter reaction внутри Python executor v3. Не доказан отдельный runtime dispatch role-orchestrator/provider-adapter workflows.

## Roadmap

### BEM-538.1 — Runtime dispatch readiness audit
Проверить наличие `workflow_dispatch`, inputs, no forbidden issue #31, transport/state writes.
PASS: audit report, workflow checks, blocker decision.

### BEM-538.2 — Dispatch bridge contract
Формализовать разрешённый bridge: Deno endpoint или existing dispatcher должен уметь запускать `role-orchestrator.yml` and `provider-adapter.yml`. Если bridge отсутствует — создать spec/blocked item, не имитировать live dispatch.
PASS: contract/spec, exact blocker if bridge absent.

### BEM-538.3 — Workflow-level synthetic dispatch proof
Если bridge available: dispatch role-orchestrator then provider-adapter, verify transport/state. Если bridge absent: record blocker and next required implementation step.
PASS: real workflow SHA/result OR exact blocker.
