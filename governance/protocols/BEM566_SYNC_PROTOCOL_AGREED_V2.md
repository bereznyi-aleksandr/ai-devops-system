# BEM-566 | Согласованный протокол синхронизации Claude ↔ GPT | V2

Дата фиксации: 2026-05-24T12:22:02Z
Источник Claude: governance/audit_mailbox/claude_to_gpt/bem857_claude_direct_response.md
Decision: APPROVED

| Раздел | Согласованное правило | Обоснование |
|---|---|---|
| Peer-модель | Внешний GPT-аудитор и внутренний Claude-аудитор равны по статусу | Оператор остаётся единственным старшим |
| Mailbox | GPT пишет Claude в `governance/audit_mailbox/gpt_to_claude/`, Claude отвечает в `governance/audit_mailbox/claude_to_gpt/` | Единый файловый канал, проверяемый коммитами |
| Реальный ответ | Ответ засчитывается только если содержит `CLAUDE RESPONSE`, решение `DECISION`, и не содержит явный blocker | Исправлено ложное отклонение фразы `Not fallback` |
| Решения | Допустимые решения: `APPROVED`, `CHANGE_REQUIRED`, `BLOCKED` | Автоматическая маршрутизация без ручной передачи |
| Разногласия | Техническое разногласие решают GPT и Claude сами; архитектурное — оператор; спор с решением оператора запрещён | Правка Claude по BEM-857 |
| Telegram | Telegram — уведомление оператору и gate для архитектурных решений, не канал передачи содержимого между агентами | Содержимое должно попадать в repo-mailbox |
| Handoff | Handoff в Curator допускается только после решения оператора | Исключает самовольную передачу в исполнение |
| Непрерывность | Отчёт не останавливает разработку; после отчёта сразу следующий шаг | Контракт внешнего аудитора |
| Workflow health | `Claude Internal Auditor Dispatcher` проверяется отдельно от содержательного APPROVED | На скриншоте есть OIDC/action warning; это P0 infra, но не отменяет прямой mailbox-response |

Status: AGREED
No issue comments.
