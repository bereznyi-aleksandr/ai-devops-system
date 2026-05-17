# BEM-536 | Internal Contour Full Development Cycle Autotest Roadmap

Дата: 2026-05-17 | 13:34 (UTC+3)

## Цель
Проверить, что внутренний контур разработки работоспособен на полном цикле: curator -> analyst -> auditor -> executor -> auditor final -> curator closure.

## Тестовая задача разработки
Создать новый development artifact `governance/internal_contour/tests/bem536/development_artifact.md`, провести его через анализ, аудит, исполнение и закрытие.

## Три задачи roadmap

### Task 1 — Curator intake + Analyst plan
Curator принимает synthetic development request, назначает analyst, analyst создаёт план реализации.
PASS: intake, analyst plan, transport records, role state updated.

### Task 2 — Auditor approval + Executor patch
Auditor проверяет план, executor создаёт development artifact.
PASS: audit approval, development artifact, execution record, SHA.

### Task 3 — Final audit + Curator closure
Auditor final проверяет artifact, curator закрывает cycle, обновляет contour_status.
PASS: final audit PASS, curator closure, done-marker, final report, blocker=null.
