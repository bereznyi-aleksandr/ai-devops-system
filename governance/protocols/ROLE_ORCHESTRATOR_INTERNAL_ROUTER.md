# BEM-598 | Role Orchestrator To Internal Contour Router

Дата: 2026-05-17 | 22:58 (UTC+3)

## Назначение

Маршрутизировать machine-readable решения из `governance/role_orchestrator/inbox/` во внутренний контур.

## Поток

role_orchestrator/inbox -> internal_contour/inbox -> internal_contour/tasks -> analyst/auditor/executor cycle.

## Правило

Решение оператора не должно зависать в role-orchestrator. Оно должно превращаться в задачу внутреннего контура.
