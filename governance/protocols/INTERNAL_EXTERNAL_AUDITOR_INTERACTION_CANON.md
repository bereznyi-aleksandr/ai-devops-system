# BEM-628 | Internal ↔ External Auditor Interaction Canon

Дата: 2026-05-18 | 07:27 (UTC+3)

## Роли

- Internal Auditor: роль внутреннего контура. Получает задачи только через `governance/internal_contour/auditor/inbox/`.
- External Auditor: независимый внешний аудитор. Не получает задачи от Analyst напрямую.

## Каналы

### Внутренний контур
Analyst → Internal Auditor: `governance/internal_contour/auditor/inbox/`
Internal Auditor → Executor: `governance/internal_contour/executor/inbox/`

### Связь аудиторов
Internal Auditor → External Auditor: `governance/audit_mailbox/internal_auditor_to_external_auditor/`
External Auditor → Internal Auditor: `governance/audit_mailbox/external_auditor_to_internal_auditor/`

## Запрет

`governance/audit_mailbox/gpt_to_claude/` и `claude_to_gpt/` являются legacy/compat lanes. Они не считаются стандартным внутренним role-bus.

## Decision rule

Если вопрос технический и решается внутри — Internal Auditor пишет report в `internal_contour/auditor/reports/`.
Если нужен внешний взгляд — Internal Auditor создаёт пакет в `audit_mailbox/internal_auditor_to_external_auditor/`.
Если внешний аудитор ответил — ответ кладётся в `audit_mailbox/external_auditor_to_internal_auditor/`, после чего Internal Auditor делает внутренний verdict.
