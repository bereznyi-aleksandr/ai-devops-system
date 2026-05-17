# BEM-548 | Next Development Roadmap for External Audit Approval

Дата: 2026-05-17 | 14:46 (UTC+3)

## Цель
Согласовать следующий план развития внутреннего контура разработки после BEM-531/BEM-541/BEM-543/BEM-545/BEM-546.

## Базовое правило архитектуры
Внешний контур пишет только куратору. Куратор валидирует задачу, передаёт её оркестратору, оркестратор назначает роли, provider-adapter выбирает провайдера только после provider probe.

## Предлагаемая дорожная карта

### BEM-548.1 — Curator runtime intake hardening
Укрепить curator intake: schema validation, duplicate trace_id protection, mandatory blocker format, source audit.
PASS: schema samples, validation report, transport records.

### BEM-548.2 — Role-orchestrator workflow parity
Перенести проверенную practical decision logic BEM-543 в постоянный контракт/workflow role-orchestrator без direct external dispatch.
PASS: workflow/contract includes curator_assignment -> analyst/auditor/executor/final audit/closure routing.

### BEM-548.3 — Provider probe integration
Интегрировать BEM-541 provider probe into provider-adapter workflow path: no reserve without failed/cancelled/timeout evidence.
PASS: provider_probe_result + provider_selection_decision + provider_selection_audit records.

### BEM-548.4 — Telegram live delivery confirmation
После ближайшего hourly run проверить `telegram_delivery_result.status=sent`; если failed — записать exact blocker and fix sender.
PASS: real sent record or exact delivery blocker.

### BEM-548.5 — Full real-flow regression test
Провести regression: external task -> curator intake -> curator assignment -> role-orchestrator -> provider probe -> roles -> Telegram delivery_result -> final report.
PASS: no synthetic shortcut; all decisions have records and SHA.

### BEM-548.6 — Monitoring/state dashboard file
Сформировать единый machine-readable файл `governance/state/contour_status.json` schema v2 для внешнего GPT/Claude/Telegram чтения.
PASS: schema v2, last run, blockers, provider, Telegram, role cycle status.
