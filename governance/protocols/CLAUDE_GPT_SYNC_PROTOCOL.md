# BEM-563 | Claude-GPT Synchronization Protocol

Дата: 2026-05-17 | 19:24 (UTC+3)
Статус: DRAFT_FOR_CLAUDE_AGREEMENT

## 1. Цель

| Наименование | Описание | Обоснование |
|---|---|---|
| Цель | Сделать синхронизацию Claude и GPT первоочередным механизмом | Оператор не должен быть передаточным звеном |
| Канал | Repo audit mailbox + reports + Telegram operator decision gate | Асинхронно, проверяемо, без ручного relay |
| Итог | Claude и GPT согласуют позицию в файлах, результат уходит оператору в Telegram | Финальное стратегическое решение принимает оператор |

## 2. Принципы

| Принцип | Решение | Обоснование |
|---|---|---|
| Equal audit | Claude и GPT равноправно обсуждают архитектуру | Оператор подтвердил совместное согласование |
| GPT implements | После согласования реализацию ведёт GPT | Экономия лимитов Claude |
| Operator final gate | Стратегический итог идёт в Telegram на решение оператора | BEM-562 |
| No separate board | Отдельная доска не создаётся | Внутренний контур и audit mailbox достаточно |
| No operator relay | Оператор не пересылает сообщения вручную | Цель автономности |

## 3. Роли синхронизации

| Роль | Provider | Обязанность |
|---|---|---|
| Curator | GPT/Codex | Создаёт sync request, следит за deadline, закрывает цикл |
| Analyst | GPT/Codex | Готовит позицию GPT, варианты, риски, вопросы |
| Auditor Claude | Claude | Даёт независимую позицию/правки/вердикт |
| Auditor GPT | GPT | Аудирует ответ Claude на соответствие контракту и repo state |
| SYSTEM writer | GitHub Action/script | Фиксирует machine-state после согласования |
| Operator | Telegram | Принимает финальное стратегическое решение |

## 4. Workflow

| Шаг | Действие | Артефакт |
|---|---|---|
| 1 | GPT формирует вопрос/позицию | `governance/audit_mailbox/gpt_to_claude/<id>.md` |
| 2 | Claude отвечает/корректирует | `governance/audit_mailbox/claude_to_gpt/<id>.md` |
| 3 | GPT делает review ответа Claude | `governance/audits/gpt_review/<id>.md` |
| 4 | Если есть консенсус, формируется decision summary | `governance/decisions/<id>.md` |
| 5 | Итог уходит оператору в Telegram | `telegram_operator_decision_required` |
| 6 | После решения оператора SYSTEM writer фиксирует state | runtime/state files |

## 5. Формат audit mailbox request

```json
{
  "schema_version": "audit_mailbox.v1",
  "message_id": "bem563_<topic>",
  "from_agent": "gpt",
  "to_agent": "claude",
  "type": "architecture_sync",
  "status": "open",
  "created_at": "YYYY-MM-DD | HH:MM (UTC+3)",
  "deadline_at": "YYYY-MM-DD | HH:MM (UTC+3)",
  "requires_operator_decision": true,
  "telegram_gate": true,
  "question": "...",
  "gpt_position": "...",
  "options": [],
  "artifacts": [],
  "expected_claude_response": "approve | approve_with_changes | reject | request_operator",
  "blocker": null
}
```

## 6. Вопросы Claude для согласования

| # | Вопрос | Позиция GPT | Что просим от Claude |
|---|---|---|---|
| 1 | Согласен ли Claude, что sync protocol должен быть первоочередным перед GitHub API migration и SYSTEM writer? | Да, без синхронизации решения будут снова идти через оператора | Approve/adjust |
| 2 | Согласен ли Claude с audit mailbox вместо отдельной доски? | Да, repo-native mailbox проще и не требует оператора-relay | Approve/adjust |
| 3 | Согласен ли Claude, что итог согласования отправляется в Telegram оператору для финального решения? | Да, это BEM-562 operator decision gate | Approve/adjust |
| 4 | Согласен ли Claude, что Curator и Analyst — обязательные GPT/Codex роли? | Да, это решения оператора BEM-557/BEM-558 | Не обсуждать существование, только интеграцию |
| 5 | Согласен ли Claude, что рутинные задачи продолжаются, а стратегические решения ждут Telegram-решения оператора? | Да | Approve/adjust |
| 6 | Какой SLA ответа Claude считать нормальным? | Предложение GPT: 3 часа для стратегических вопросов, timeout -> GPT draft + Telegram note | Утвердить SLA |
| 7 | Какой статус считать консенсусом? | `approved_by_both`, `approved_with_changes`, `disagreement_requires_operator` | Утвердить статусы |
| 8 | Что делать при разногласии Claude и GPT? | Сформировать две позиции + рекомендацию + Telegram operator decision | Утвердить процесс |

## 7. Ответы GPT на ключевые вопросы

| Тема | Ответ GPT | Обоснование |
|---|---|---|
| Нужна ли отдельная board | Нет | Дублирует внутренний контур и создаёт ручной relay |
| Где хранить обсуждение | `governance/audit_mailbox/` | Асинхронно, repo-visible, audit-friendly |
| Кто создаёт запрос | Curator(GPT/Codex) | Curator — единая точка входа |
| Кто готовит аналитическую позицию | Analyst(GPT/Codex) | Аналитик обязательная активная роль |
| Кто принимает финальное решение | Operator через Telegram | Стратегическое решение не автоматизируем без оператора |
| Кто фиксирует machine-state | SYSTEM writer | После operator decision |

## 8. Telegram-шаблон результата согласования

```text
BEM-<N> | CLAUDE-GPT SYNC RESULT | YYYY-MM-DD | HH:MM (UTC+3)

Этап: <X>/<Y> (<Z%>)
Дорожная карта: <X>/<Y> (<Z%>)

Чек-лист:
✅ GPT позиция зафиксирована
✅ Claude позиция зафиксирована
✅ Разногласия/правки описаны
⚠️ Требуется решение оператора

Наименование | Описание | Обоснование
Вопрос | <тема> | <почему стратегический>
Позиция GPT | <кратко> | <артефакт>
Позиция Claude | <кратко> | <артефакт>
Рекомендация | <вариант> | <обоснование>
Решение оператора | ожидается | стратегический gate
```

## 9. PASS criteria для BEM-563

| Критерий | Статус |
|---|---|
| Протокол создан | PASS |
| Audit mailbox request создан | PASS |
| Telegram operator decision message queued | PASS |
| Вопросы Claude сформулированы | PASS |
| Ответы GPT сформулированы | PASS |


---

# BEM-564 CORRECTION | Agreed External Decision Goes To Curator

Дата: 2026-05-17 | 20:00 (UTC+3)

| Наименование | Описание | Обоснование |
|---|---|---|
| Correction | После согласования Claude-GPT или подтверждения оператором решение передаётся Curator, не Analyst напрямую | Curator — единая точка входа внутреннего контура |
| Internal route | Curator -> Role-orchestrator -> Analyst -> Auditor -> Executor -> Final audit -> Curator closure | Внутренний контур сам назначает следующие роли |
| Boundary | Внешний аудит только согласует; внутренний контур выполняет | Не смешивать контуры |
