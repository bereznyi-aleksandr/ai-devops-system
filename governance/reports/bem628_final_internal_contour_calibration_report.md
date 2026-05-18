# BEM-628 | Final Internal Contour Calibration Report

Дата: 2026-05-18 | 07:27 (UTC+3)

## Status
calibrated_with_known_runtime_blockers

## Direct answers
### Будем ли использовать mailbox для общения между ролями?
Нет. Внутренние роли используют internal role-bus. Mailbox только для Internal Auditor ↔ External Auditor.
Evidence: governance/protocols/ROLE_COMMUNICATION_CANON.md

### Почему не сработал стандартный механизм?
В BEM-605 была архитектурная ошибка: analyst-to-Claude был отправлен через mailbox. BEM-625 исправил это: создан правильный internal auditor inbox package и misroute annotation.
Evidence: governance/internal_contour/auditor/inbox/bem625_bem605_hourly_report_internal_auditor_review.json

### Сработал ли основной Claude контур?
Не доказан. Provider gate зафиксировал primary not proven и выбрал reserve route. Нельзя ставить PASS без Claude-authored runtime artifact.
Evidence: governance/provider_gates/bem610_provider_route_decision.json

### Почему Deno был в цепочке?
Deno использовался только как доступный внешнему GPT транспорт к repo. Он не является внутренним Executor. Внутренний Executor должен фиксироваться отдельно через execution_type/adapter.
Evidence: governance/protocols/ROLE_EXECUTION_EVIDENCE_CANON.md

### Что налажено сейчас?
Добавлены role-bus canon, auditor interaction canon, execution evidence canon, architecture lint, BEM-605 repair, legacy mailbox annotation.
Evidence: governance/state/internal_contour_architecture_lint.json

## Calibrated architecture
1. Operator → Curator GPT via accepted entrypoint.
2. Curator → Role Orchestrator through `governance/role_orchestrator/inbox/`.
3. Role Orchestrator → internal task registry.
4. Analyst GPT → Internal Auditor through `governance/internal_contour/auditor/inbox/`.
5. Internal Auditor decides internally or opens auditor-to-auditor sync mailbox.
6. External Auditor replies only through external-to-internal auditor lane.
7. Internal Auditor issues verdict to Executor inbox.
8. Executor runs with explicit execution_type and provider evidence.
9. Selftest and monitoring report must state artifact/live-provider distinction.

## Current runtime facts
- Internal role-bus lint: pass
- Selected provider: gpt_reserve
- Reserve used: True
- Live delivery status: live_sent

## Remaining blockers
- CLAUDE_PRIMARY_RUNTIME_NOT_PROVEN: Need Claude-authored runtime artifact before selecting Claude primary.
- LIVE_TELEGRAM_DELIVERY_NOT_CONFIRMED: Need telegram_delivery=sent in repo state.

## Result
The internal contour communication model is now repaired and guarded by lint. The auditor mailbox boundary is defined. The system still must prove Claude runtime and Telegram live delivery before claiming full primary-contour production PASS.
