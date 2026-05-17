# BEM-547 | Next Development Contours Roadmap for Claude Review

Дата: 2026-05-17 | 14:44 (UTC+3)

## Цель
Согласовать следующий план развития контуров системы разработки после серии BEM-531/BEM-535/BEM-541/BEM-543/BEM-546.

## Предлагаемый следующий план

| Этап | Название | Цель | PASS-критерий |
|---|---|---|---|
| BEM-548 | Live Telegram delivery confirmation | Дождаться/проверить реальный `telegram_delivery_result.status=sent` после запуска `curator-hourly-report.yml` | Transport содержит `status=sent`, сообщение реально доставлено |
| BEM-549 | Curator runtime intake hardening | Превратить curator intake contract в устойчивую обработку pending-задач: validation, dedupe, assignment, final result | Тестовая задача проходит через curator intake без ручной эмуляции цепочки |
| BEM-550 | Role orchestrator workflow alignment | Синхронизировать file-level proven routing logic BEM-543 с `.github/workflows/role-orchestrator.yml` | Workflow содержит те же правила routing и пишет `role_orchestrator_decision` |
| BEM-551 | Provider adapter live outcome integration | Связать `claude.yml outcome/status` с provider probe/selection decision без forced reserve | Claude active -> Claude, Claude failed/cancelled/timeout -> GPT reserve, все решения audit-recorded |
| BEM-552 | Internal contour live E2E | Провести live practical task: curator intake -> orchestrator workflow -> provider adapter -> role result -> curator closure | Transport/state/report подтверждают не synthetic, а workflow-level цикл |
| BEM-553 | Telegram report quality and throttling | Настроить канонический формат hourly Telegram report, dedupe и throttling | Нет spam, есть hourly status, blocker and next action |
| BEM-554 | Cleanup after test storm | Архивировать test artifacts, устаревшие reports и wrong-direction artifacts без нарушения доказательств | manifest архива, active контур не сломан |

## Вопросы на согласование Claude
| Вопрос | Предложение GPT | Обоснование |
|---|---|---|
| Приоритет | Сначала BEM-548, затем BEM-549/BEM-550 | Live Telegram уже подключён, нужно закрыть delivery proof |
| Orchestrator | Перенести доказанную BEM-543 logic в workflow, не давать external direct dispatch | Архитектура Claude: external -> curator only |
| Provider | Убрать любые forced reserve сценарии без probe evidence | Ошибка BEM-540 уже исправлена BEM-541 |
| Cleanup | Выполнить после стабилизации live E2E | Иначе можно удалить нужные debugging artifacts слишком рано |
