# BEM-596 | Curator Inbox Router

Дата: 2026-05-17 | 22:53 (UTC+3)

## Назначение

Решение оператора после попадания в `governance/curator/inbox/` автоматически маршрутизируется во внутренний контур через role-orchestrator inbox.

## Поток

operator_decisions -> curator/inbox -> role_orchestrator/inbox -> internal contour.

## Правило

Куратор не должен быть ручным буфером. Любой curator intake должен получить machine-readable route package.
