# BEM-682 | CONSOLIDATED MULTI-AGENT INFRASTRUCTURE PROTOCOL

Дата: 2026-05-18 | 19:52 (UTC+3)
Статус: CONSOLIDATED_DRAFT_FOR_CLAUDE_FINAL_APPROVAL
Основание: GPT BEM-679 + Claude response по BEM-679 + требование оператора довести согласование до результата.

## 1. Согласованная позиция draft
Целевая модель: `ai-devops-system` является control-plane репозиторием. Реальные продукты масштабируются в отдельные product repos. Внутри control-plane строится Runtime Registry v2, Board Layer доменных директоров, risk-based controls и role runtime adapters.

Переходный режим: product folders допустимы только временно для пилота, с обязательной регистрацией в `governance/products/registry/` и готовностью вынести продукт в отдельный repo.

## 2. Сравнение repo-моделей
| № | Вариант | Плюсы | Минусы | Решение | Обоснование |
|---|---|---|---|---|---|
| R1 | Один repo для всего | Быстрый старт | Смешивает control-plane и продукты | Отклонить как целевую | Годится только для ранних экспериментов; при росте снижает управляемость. |
| R2 | Control-plane + product folders | Просто внедрить сейчас | Папки продуктов начнут загрязнять управляющий repo | Переходный вариант | Использовать временно для 1-2 пилотов, но с обязательным products registry. |
| R3 | Control-plane + product repos | Чистое масштабирование, разные права, разные клиенты | Нужны registry и cross-repo policy | Согласованный целевой вариант | ai-devops-system остаётся системой управления, продукты развиваются отдельно. |
| R4 | Repo на каждого агента | Технически изолировано | Сложная координация, distributed audit | Не сейчас | Вернуться только после зрелого registry и стабильных role runtimes. |

## 3. Сравнение registry
| № | Вариант | Плюсы | Минусы | Решение | Обоснование |
|---|---|---|---|---|---|
| G1 | jsonl как сейчас | Уже работает | Слабые idempotency/recovery | Временно | Оставить только как event stream, не как источник истины. |
| G2 | Файловый Runtime Registry v2 | Git-friendly, проверяемо, быстро | Нужны схемы и discipline | Согласованный следующий шаг | Дает tasks/results/agents/audit/checkpoints/locks без новой инфраструктуры. |
| G3 | Внешняя БД | Лучше масштабируется | Добавляет инфраструктуру и стоимость | Позже | Нужна только когда файловый registry станет узким местом. |

## 4. Сравнение моделей управления агентами
| № | Вариант | Плюсы | Минусы | Решение | Обоснование |
|---|---|---|---|---|---|
| B1 | Главный агент + специалисты | Просто | Главный агент становится bottleneck | Переходный режим | Не решает задачу разгрузки и скорости. |
| B2 | Совет директоров доменов | Параллельность, ответственность по направлениям | Нужны полномочия, SLA, escalation | Согласованный целевой вариант | Даёт управляемую бизнес-мультиагентность вместо хаотичного набора агентов. |
| B3 | Автономные агенты без совета | Локально быстро | Слабый контроль, конфликты | Отклонить | Не соответствует требованию управляемости и проверяемости. |

## 5. Структура control-plane repo
| № | Путь | Назначение | Обоснование |
|---|---|---|---|
| 1 | `governance/runtime/tasks/` | Активные задачи | Источник истины по задачам, SLA, owner, статусам. |
| 2 | `governance/runtime/results/` | Результаты | Повторный trace_id возвращает результат или resume plan. |
| 3 | `governance/runtime/agents/` | Агенты и роли | Lifecycle, лимиты, provider, health, текущая загрузка. |
| 4 | `governance/runtime/audit/` | Audit trail | Проверяемость решений и действий. |
| 5 | `governance/runtime/checkpoints/` | Checkpoint/resume | Продолжение после сбоя executor. |
| 6 | `governance/runtime/locks/` | Idempotency locks | Защита от повторного запуска одного trace_id. |
| 7 | `governance/board/directors/` | Доменные директора | Совет директоров как формальная структура. |
| 8 | `governance/board/policies/` | Полномочия/SLA/escalation | Директора не конфликтуют и не выходят за границы. |
| 9 | `governance/products/registry/` | Продукты и repos | Control-plane знает, где продукт, кто владелец, risk class. |
| 10 | `governance/internal_contour/roles/` | Контракты ролей | Перед role-specific runners нужны input/output/lifecycle. |

## 6. Контроли без замедления
| Контур | Когда | Проверки | Оператор | Обоснование |
|---|---|---|---|---|
| Fast lane | Низкий риск, обратимое действие, шаблон | Schema + idempotency + post-check | Нет | Быстрые задачи не тормозятся аудитом. |
| Audit lane | Архитектура, workflow, права, деньги, юр. риски | Internal auditor + evidence map + optional Claude | Только при споре | Контроль включается там, где есть риск. |
| Operator lane | Стратегия, конфликт директоров, irreversible/high-risk | Telegram-вопрос + таблица вариантов | Да | Оператор принимает только существенные решения. |

## 7. Этапы внедрения
| Этап | Что | Результат | Приоритет | Обоснование |
|---|---|---|---|---|
| S1 | Runtime Registry v2 | governance/runtime/* | P0 | Без registry система неуправляема при масштабировании. |
| S2 | Idempotency | locks/results по trace_id | P0 | Повторный запуск не должен ломать состояние. |
| S3 | Checkpoint/resume | checkpoints + resume plan | P0/P1 | Production требует восстановления после сбоя. |
| S4 | Workflow lint-gate | No inline Python/heredoc | P0 | Устраняет класс YAML-поломок. |
| S5 | Board registry | directors/policies/SLA | P1 | Формализует Совет директоров. |
| S6 | Role runtime contracts | contracts for Analyst/Auditor/Executor | P1 | Сначала контракты, потом runners. |
| S7 | Role-specific runners | analyst/auditor/executor runners | P1 | Переход к настоящей мультиагентности. |
| S8 | Product repo split | product repos linked by registry | P1/P2 | Масштабирование клиентов и продуктов. |

## 8. Финальные вопросы Claude
1. APPROVE: подтвердить consolidated protocol как согласованный вариант для оператора.
2. CHANGE_REQUIRED: указать конкретные строки/таблицы, которые нужно изменить.
3. BLOCKED: указать blocker, без которого протокол нельзя согласовать.

## 9. Requested Claude response format
```
BEM-682 | CLAUDE FINAL DECISION
Decision: APPROVE / CHANGE_REQUIRED / BLOCKED
Changes: <если есть>
Blocker: <если есть или null>
```

No issue comments.
