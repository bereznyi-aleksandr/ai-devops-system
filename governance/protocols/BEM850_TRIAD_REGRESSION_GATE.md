# BEM-850 | Triad Regression Gate

Дата: 2026-05-24 | 21:42 (UTC+3)
Статус: active_policy

## Правило

Любой новый цикл GPT ↔ Claude считается успешным только при наличии всех трёх доказательств:

| Proof | Файл / признак | PASS условие |
|---|---|---|
| Dispatch result | `governance/workflow_dispatch_results/*.status.json` | Есть status-файл запуска Claude dispatcher |
| Claude runtime | `governance/state/claude_inbound_mailbox_workflow_state.json` | Есть `started_at` или `completed_at` |
| Real response | `governance/audit_mailbox/claude_to_gpt/*` | Есть `Decision:` и это не `NOT CLAUDE APPROVAL` / не runtime blocker |

## Запрет

Без triad-proof нельзя писать `APPROVED`, нельзя повышать протокол до финального статуса и нельзя считать задачу согласования завершённой.

## Следующее действие

Поддерживать этот gate как обязательную проверку перед каждым отчётом по согласованию.
