# BEM-540 | Full System Autotest Roadmap

Дата: 2026-05-17 | 14:04 (UTC+3)

## Цель
Проверить полную работу системы на тестовой roadmap без нарушения архитектуры: внешний контур пишет только curator, curator проводит внутренний цикл, transport/state фиксируют результат, provider failover и Telegram outbox проверяются synthetic/runtime-safe способом.

## Архитектурное правило
External GPT/Claude/Telegram -> curator only. Direct dispatch internal workflows by external contour is prohibited.

## Roadmap из 4 задач

### Task 1 — System preflight + test roadmap
Проверить наличие контрактов, state, transport, provider state, Telegram hourly contract/workflow. Создать test roadmap and curator intake.
PASS: all required files exist, curator intake record appended, blocker=null.

### Task 2 — Curator-driven internal development cycle
Curator routes to analyst -> auditor -> executor -> auditor final -> curator closure on a test artifact.
PASS: all role artifacts exist, role state and transport updated.

### Task 3 — Provider failover + Telegram outbox synthetic system check
Проверить Claude failed -> GPT reserve decision and generate canonical Telegram outbox payload without secrets/live send.
PASS: provider state updated, telegram_outbox.jsonl appended, no secrets.

### Task 4 — Final system audit and closure
Собрать доказательства всех подсистем, обновить contour_status, закрыть roadmap.
PASS: final report, done-marker, blocker=null.
