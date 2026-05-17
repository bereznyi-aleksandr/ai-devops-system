# BEM-542 | Real Internal Orchestrator Test Roadmap

Дата: 2026-05-17 | 14:12 (UTC+3)

## Причина
BEM-540 был synthetic test. Он не доказал, что реальный внутренний оркестратор сам читает вход, выбирает роль и ведёт цикл.

## Цель
Проверить рабочую модель системы на практике: задача входит через curator intake, затем internal role-orchestrator принимает решение о следующей роли, provider-adapter выбирает провайдера, executor создаёт artifact, auditor/curator закрывают цикл.

## Архитектурная граница
Внешний контур не должен напрямую управлять ролями. Но тест должен проверять внутреннюю orchestration logic, а не ручную эмуляцию ролей.

## Roadmap

### BEM-542.1 — Orchestrator readiness and gap audit
Проверить, что role-orchestrator.yml и provider-adapter.yml имеют реальную decision/failover logic, а не только append records.
PASS: report with exact gaps.

### BEM-542.2 — Implement real orchestrator test harness
Добавить internal test harness, который читает curator intake and transport, применяет те же routing rules, что role-orchestrator, и пишет решения как internal orchestrator records. Если возможно — улучшить role-orchestrator contract/workflow.
PASS: orchestrator_decision artifact produced from input, not hardcoded role chain.

### BEM-542.3 — Provider probe and adapter decision
Перед reserve-switch выполнить provider probe decision: Claude active -> Claude selected; Claude failed -> GPT reserve.
PASS: provider_selection_decision records for both branches.

### BEM-542.4 — End-to-end practical test
Запустить тестовую задачу через curator intake, orchestrator decision, provider adapter, executor artifact, final closure.
PASS: transport/state/report show role decisions created by orchestrator logic.

### BEM-542.5 — Final system report
Сформировать honest PASS/BLOCKER: что реально работает, что остаётся runtime-limited.
