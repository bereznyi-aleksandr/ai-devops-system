# BEM-564 | External Audit Result -> Internal Curator Handoff

Дата: 2026-05-17 | 20:00 (UTC+3)

## Решение оператора

| Наименование | Описание | Обоснование |
|---|---|---|
| Внешнее обсуждение | Claude и GPT обсуждают вопрос через audit mailbox | Оператор не должен быть передаточным звеном |
| Финальное решение | Если вопрос стратегический, итог уходит оператору в Telegram | BEM-562 operator decision gate |
| Передача во внутренний контур | Согласованное или утверждённое решение передаётся куратору | Curator — единая точка входа |
| Дальнейший маршрут | Curator(GPT/Codex) -> Orchestrator -> Analyst(GPT/Codex) -> Auditor -> Executor -> Final audit -> Curator closure | Внутренний контур сам распределяет роли |
| Запрет | Нельзя передавать согласованное внешним аудитом решение напрямую аналитику или исполнителю | Это обходит куратора и ломает архитектуру единого входа |

## Правильная цепочка

```text
External audit discussion:
GPT <-> audit_mailbox <-> Claude
        |
        v
if strategic: Telegram operator decision
        |
        v
Approved / agreed decision
        |
        v
Curator(GPT/Codex)
        |
        v
Role-orchestrator
        |
        v
Internal contour:
Analyst(GPT/Codex) -> Auditor(Claude/GPT) -> Executor(provider) -> Final audit -> Curator closure
```

## Правило
Внешний аудит согласует решение. Внутренний контур исполняет. Мост между ними — только Curator.


---

# BEM-565 CORRECTION | External and Internal Auditors Are Peers

Дата: 2026-05-17 | 20:02 (UTC+3)

| Наименование | Описание | Обоснование |
|---|---|---|
| Correction | Внешний аудитор не “согласует сверху”; внешний и внутренний аудиторы равноправно обсуждают и приходят к решению | Решение оператора |
| Final authority | Старший только оператор | Оператор принимает стратегическое финальное решение |
| Handoff | Совместное решение аудиторов или решение оператора передаётся куратору | Curator — единая точка входа |
| Route | Curator -> Role-orchestrator -> internal contour | Внутренний контур сам исполняет через свои роли |
