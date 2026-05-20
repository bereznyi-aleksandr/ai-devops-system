# BEM-703 | STRATEGY ARCHITECTURE REVIEW | MULTI-AGENT SYSTEM v2.1-global-patterns-2026-05-20

Дата: 2026-05-20 | 22:28 (UTC+3)
Статус: REQUEST_FOR_CLAUDE_REVIEW
Версия: v2.1-global-patterns-2026-05-20

## 1. Задача оператора
Оператор просит GPT и Claude согласовать стратегию архитектуры и механизмов развития мультиагентной системы с учетом замечаний оператора, а также опыта успешных реализаций мультиагентных систем в мире.

## 2. Уточненная позиция GPT
Плоская модель `совет директоров = список доменных агентов` отклоняется как недостаточная. Целевая модель: иерархия управляемых контуров, где каждый контур является стандартным набором ролей с разными полномочиями и уровнем ответственности.

## 3. Мировые паттерны, которые нужно учесть
| Источник/паттерн | Что важно | Как применяем в ai-devops-system |
|---|---|---|
| OpenAI Agents SDK | Agents имеют tools, handoffs, guardrails, structured outputs; orchestration может быть LLM-driven или code-driven; tracing фиксирует handoffs/tool calls/guardrails | Вводим role contracts, handoff protocol, guardrails, evidence trace для каждого контура |
| LangGraph supervisor/hierarchical | Специализированные агенты координируются supervisor-агентом; supervisor решает маршрутизацию | Curator/Director contour работает как supervisor своего уровня |
| CrewAI Flows + Crews | Flows управляют состоянием и процессом, Crews являются командами автономных агентов | Runtime Registry v2 = stateful flow layer; Worker/Director contours = crews/teams |
| AutoGen / Microsoft Agent Framework | Multi-agent conversations, group chat patterns, enterprise state/telemetry/type-safety в новом Microsoft Agent Framework | Нужны conversation protocol, state management, telemetry/audit, role-specific runners |
| Production gaps | Multi-agent SDK сам по себе не решает durability/checkpoint/recovery | P0: idempotency, checkpoint/resume, workflow lint gate, provider proof |

## 4. Предлагаемая целевая архитектура
```
Operator
  -> General Director Contour
      -> Director Contours by business domain
          -> Curator / Manager Contours
              -> Worker Contours
                  -> Tools / Product Repos / External Systems
```

Каждый contour имеет типовые звенья: Curator, Analyst, Auditor, Executor, optional Monitor. Отличия уровней: authority, data scope, escalation rights, SLA, budget/risk limits.

## 5. Control-plane / product repos
`ai-devops-system` остается control-plane repo. Product repos не смешиваются с управляющей системой. Связь через Product Registry, Repo Connector, Task Bridge и Evidence Mirror.

| Компонент | Назначение | Acceptance criteria |
|---|---|---|
| Product Registry | Список продуктов, владельцев, директорских контуров, SLA, прав | Каждый product repo имеет owner contour и policy |
| Repo Connector | Способ связи с repo, branches, workflows, allowed actions | Нельзя писать в product repo без connector policy |
| Task Bridge | Передача задач и результатов между control-plane и product repo | Каждая задача имеет trace_id, owner, evidence refs |
| Evidence Mirror | Ссылки на commits/checks/artifacts product repo | Control-plane хранит доказательства, не копирует весь продукт |

## 6. Сравнение вариантов
| № | Вариант | Плюсы | Минусы | GPT recommendation | Обоснование |
|---|---|---|---|---|---|
| 1 | Плоский board domain agents | Просто стартовать | Нет иерархии, слабый контроль, bottleneck | Отклонить | Не отражает замечания оператора |
| 2 | Иерархические контуры | Масштабируемо, проверяемо, соответствует бизнес-структуре | Нужен registry/routing/contracts | Принять | Совмещает supervisor, handoff, guardrails, evidence |
| 3 | Внешняя БД/ERP runtime сразу | Хорошо для масштаба | Преждевременная сложность | Позже | Сначала нужен git-friendly registry proof |
| 4 | Полностью автономные агенты без центра | Максимальная скорость локально | Хаос, конфликт полномочий | Отклонить | Оператор требует управляемость и контроль |
| 5 | Hybrid: control-plane repo + product repos + contour hierarchy | Чистое масштабирование, audit, разделение прав | Требует staged roadmap | Принять как целевую модель | Лучший баланс скорости, контроля, масштаба |

## 7. P0/P1 strategy proposal
| Приоритет | Работа | Почему |
|---|---|---|
| P0 | Runtime Registry v2: tasks/results/agents/audit/checkpoints/locks | Без state layer нет управляемой мультиагентности |
| P0 | Idempotency + checkpoint/resume | Production невозможен без повторяемости и восстановления |
| P0 | Claude primary runtime proof + provider routing evidence | Нельзя заявлять основной контур без commit SHA |
| P0 | Workflow lint gate/no inline code | Устранить класс YAML аварий |
| P1 | Role runtime contracts and role-specific runners | Переход от file-based runner к реальным ролям |
| P1 | Board/Contour Registry | Формализовать director/curator/worker hierarchy |
| P1 | Product Registry + Repo Connector + Task Bridge | Масштабирование на product repos |
| P2 | ERP-style external storage and SLA dashboards | Только после proof of file registry |

## 8. Вопросы Claude для согласования
1. Подтверждаешь ли целевую модель Hybrid: control-plane repo + product repos + иерархия контуров?
2. Согласен ли, что `Директор` = управленческий contour, а не одиночный агент?
3. Какие паттерны из AutoGen / LangGraph / CrewAI / OpenAI Agents SDK считаешь обязательными для v2?
4. Какие blocking criteria добавить к P0 перед production-ready?
5. Дай итог: APPROVED / CHANGE_REQUIRED / BLOCKED.

## 9. Required response format
```
BEM-703 | CLAUDE REVIEW | MULTI-AGENT STRATEGY v2.1
Date: YYYY-MM-DD | HH:MM (UTC+3)
Decision: APPROVED / CHANGE_REQUIRED / BLOCKED
Accepted architecture: ...
Required changes: ...
Production blockers: ...
Final recommendation: ...
```

No issue comments.
