# BEM-846 | Multi-Agent Development Protocol | Human-readable table

Дата: 2026-05-24 | 21:38 (UTC+3)
Версия: v1.0
Статус: promoted_after_evidence_marker

| Раздел | Согласованное правило | Обоснование | Proof / Gate |
|---|---|---|---|
| Цель системы | GPT-внешний аудитор управляет roadmap, Claude-внутренний аудитор даёт независимое ревью, Codex Runner вносит изменения в repo | Разделение ролей снижает риск самоподтверждения | Реальный ответ Claude + commit proof |
| Канал записи | Все изменения в repo идут через Deno → Codex Runner → commit | Оператор не должен быть routine relay | `governance/codex/results/<trace>.json` + commit SHA |
| Mailbox | GPT пишет запросы в `gpt_to_claude`, Claude отвечает в `claude_to_gpt` | Асинхронное согласование без issue comments | Файл ответа с `Decision:` |
| PASS-запрет | PASS запрещён без трёх proof: dispatch-result, Claude runtime-state, real Claude response | Исключает фиктивные APPROVED и blocker-файлы | BEM-819 single smoke contract |
| Fallback-файлы | `NOT CLAUDE APPROVAL` и runtime blocker не считаются ответом Claude | Это диагностика, а не аудит | Фильтр real response |
| Очередь dispatch | Битый JSON не валит runner: файл архивируется, создаётся status-result | Один плохой queue item не должен блокировать систему | BEM-827 hardened processor |
| Непрерывность | Отчёт не завершает roadmap; перед checkpoint создаётся следующий active task/pending/handoff | Исключает остановку после `final` | BEM-762/BEM-763 guard |
| Telegram/уведомления | Уведомления должны сообщать только изменения; при отсутствии изменений коротко: «Изменений за отчетный период нет» | Снижает шум | Hourly curator report gate |
| Operator role | Оператор не нажимает routine-confirmation и не переносит ответы между агентами | Убирает ручной relay | BEM-744 no UI confirmation rule |
| Следующий P0 | Довести real Claude response до финального протокола, затем закрепить smoke-test как обязательный regression gate | Без regression gate проблема повторится | BEM-846 → BEM-847 |

## Открытые вопросы

| Вопрос | Статус | Следующее действие |
|---|---|---|
| Финальный текст Claude-аудита | Требует финальной проверки содержимого real response | BEM-847 parse response evidence |
| Автономный wake без оператора | Частично реализован через Deno/Codex queue | Закрепить regression smoke |
| Документ для оператора | Этот файл является читаемой таблицей v0.1 | После проверки сделать v1.0 |

## Promotion evidence

- BEM-848 marker: `governance/state/bem848_PROTOCOL_CAN_ADVANCE.marker`
- Promoted at: 2026-05-24 | 21:41 (UTC+3)
- Rule: reports do not stop development; next active regression gate is required.
