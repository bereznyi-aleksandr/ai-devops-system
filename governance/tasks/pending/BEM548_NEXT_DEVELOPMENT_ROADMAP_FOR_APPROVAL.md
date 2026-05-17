# BEM-548 | Next Development Roadmap Approved by Claude

Дата: 2026-05-17 | 14:51 (UTC+3)

## Статус аудита
Claude одобрил BEM-548 с двумя правками:
1. BEM-546 не ждать: если outbox имеет `ready_to_send`/`queued_for_sender`, technical wiring считается завершённым; live proof появится на первом hourly run.
2. Full regression разделить на два этапа: 5a synthetic и 5b live.

## Архитектурное правило
Внешний контур пишет только куратору. Куратор валидирует вход, передаёт в role-orchestrator, оркестратор назначает роли, provider-adapter выбирает провайдера только после provider probe.

## Roadmap — 7 этапов

### BEM-548.1 — Curator runtime intake hardening
Schema validation, duplicate trace_id protection, mandatory blocker format, source audit.
PASS: validation samples, report, transport records.

### BEM-548.2 — Role-orchestrator workflow parity
Перенести проверенную BEM-543 decision logic в постоянный contract/workflow parity без direct external dispatch.
PASS: workflow/contract routes curator_assignment -> analyst/auditor/executor/final audit/closure.

### BEM-548.3 — Provider probe integration
Интегрировать BEM-541 provider probe into provider-adapter workflow path.
PASS: provider_probe_result + provider_selection_decision + provider_selection_audit records.

### BEM-548.4 — Telegram delivery confirmation without waiting
Проверить outbox readiness. Не ждать hourly run.
PASS: ready_to_send/queued_for_sender record exists or exact blocker.

### BEM-548.5a — Synthetic regression
Все записи файловые, без live API.
PASS: external -> curator -> orchestrator -> provider probe -> roles -> telegram delivery synthetic -> final.

### BEM-548.5b — Live regression
Реальный live check: если Telegram sent уже есть — PASS; если нет — exact blocker without stopping other development.
PASS: `telegram_delivery_result.status=sent` or exact blocker `WAITING_FOR_HOURLY_LIVE_DELIVERY`.

### BEM-548.6 — Monitoring/state dashboard v2
Stable `contour_status.json` schema v2 for GPT/Claude/Telegram readers.
PASS: schema v2 with last run/provider/Telegram/blockers.
