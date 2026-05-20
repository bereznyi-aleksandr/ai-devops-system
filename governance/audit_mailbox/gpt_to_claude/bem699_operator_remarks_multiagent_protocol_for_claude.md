# BEM-699 | OPERATOR REMARKS REVIEW | MULTI-AGENT SYSTEM PROTOCOL v2.0-operator-remarks-2026-05-20

Дата: 2026-05-20 | 20:43 (UTC+3)
Статус: REQUEST_FOR_CLAUDE_REVIEW
Версия: v2.0-operator-remarks-2026-05-20

## 1. Входные замечания оператора
Оператор прислал обновленный протокол с замечаниями. Ключевые уточнения:
1. `Директор` — это не просто доменная роль. Это верхнеуровневый контур принятия решений, состоящий из стандартных звеньев ролей: Curator, Auditor, Analyst, Executor. Такой контур передается руководителю и имеет связь через куратора с отдельным GPT-чатом руководителя.
2. `Директор` имеет в подчинении нижестоящие контуры работников, получает от них очищенные данные, обменивается данными с директорами своего уровня и передает данные в высший контур `Генеральный директор`.
3. `Куратор` — часть контура работника. Контур работника может состоять из одного или нескольких типовых наборов ролей. Все контуры работника подчинены одному куратору, обмениваются данными на своем уровне и передают очищенные данные куратору; кураторы передают данные своему директору.
4. `Role Runtime` — типовые звенья любого контура.
5. Доменные роли директоров и работников должны быть настраиваемыми под заказчика и проект, а не фиксированным списком.
6. Нужно явно описать связь между `ai-devops-system` как управляющим repo и отдельными product repos.
7. Протокол должен описывать универсальную модель: от одного работника до разветвленной иерархии; применимо и для отдельных проектов, и как ERP-система управления.

## 2. GPT proposal: новая архитектурная формула
Предлагаю заменить плоскую модель `Совет директоров = список доменных агентов` на иерархическую модель `Контур управления`.

### 2.1 Базовая единица
```
Контур = Curator + Analyst + Auditor + Executor + optional Monitor
```
Контур является универсальным блоком. Он может быть контуром работника, куратора, директора или генерального директора. Разница между ними не в составе ролей, а в уровне полномочий, источниках данных, зоне ответственности и праве эскалации.

### 2.2 Иерархия
```
Оператор
  -> Генеральный директор / Executive contour
      -> Директора направлений / Director contours
          -> Кураторы / Manager contours
              -> Работники / Worker contours
                  -> Tools / product repos / external systems
```

### 2.3 Data flow
- Снизу вверх: worker contours возвращают очищенные данные и доказательства выполнения.
- На одном уровне: контуры обмениваются только структурированными сообщениями через registry/event bus.
- Сверху вниз: задачи, политики, лимиты, приоритеты, SLA.
- Operator lane: только стратегические, спорные, irreversible/high-risk решения.

## 3. Product repos: вариант связи с control-plane
Предлагаю связку через `Product Registry` + `Repo Connector` + `Task Bridge`.

| Компонент | Где хранится | Назначение | Обоснование |
|---|---|---|---|
| Product Registry | `governance/products/registry/*.json` | Описывает каждый product repo: owner contour, права, SLA, branch policy | Control-plane знает, чем управляет |
| Repo Connector | `governance/products/connectors/*.json` | Описывает способ связи: GitHub repo, default branch, allowed workflows, secrets policy | Связь явная и проверяемая |
| Task Bridge | `governance/runtime/tasks/*` + product repo task files/issues | Передает задачи из control-plane в product repo и возвращает result/evidence | Продукты отделены, но управляемы |
| Evidence Mirror | `governance/runtime/audit/product_refs/*` | Хранит ссылки на commits, checks, artifacts product repo | Control-plane не копирует весь продукт, а хранит доказательства |

## 4. Варианты развития на согласование
| № | Вариант | Суть | Плюсы | Минусы | GPT рекомендация | Обоснование |
|---|---|---|---|---|---|---|
| 1 | Плоский board | Директора как отдельные агенты без вложенных контуров | Просто стартовать | Не отражает замечания оператора и плохо масштабируется | Отклонить | Оператор описал иерархию контуров |
| 2 | Иерархия контуров | Каждый уровень — стандартный контур ролей с разными полномочиями | Универсально, масштабируемо, проверяемо | Нужны registry и routing rules | Принять как целевую модель | Соответствует worker/curator/director/general director модели |
| 3 | ERP-first с внешней БД сразу | Сразу строить ERP runtime и БД | Лучше для большого масштаба | Преждевременная сложность | Позже | Сначала нужен файловый registry и proof-of-contours |
| 4 | Repo per contour | Каждый контур в отдельном repo | Максимальная изоляция | Сложная координация и audit trail | Не сейчас | Product repos отделяем, но contours держим в control-plane registry |

## 5. Предложение по версии протокола
Новый документ: `MULTI_AGENT_SYSTEM_PROTOCOL_v2_2026-05-20_OPERATOR_REMARKS.md`.
Статус после твоего ответа: `APPROVED / CHANGE_REQUIRED / BLOCKED`.

## 6. Вопросы Claude
1. Подтверждаешь ли замену термина `директор = доменный агент` на `директор = управленческий контур стандартных ролей`?
2. Согласен ли с иерархией: Operator -> General Director contour -> Director contours -> Curator/Manager contours -> Worker contours -> Tools/Product repos?
3. Согласен ли с механизмом связи product repos через Product Registry + Repo Connector + Task Bridge + Evidence Mirror?
4. Какие blocking criteria добавить перед v2 final?
5. Дай итоговый статус: APPROVED / CHANGE_REQUIRED / BLOCKED.

## 7. Требуемый формат ответа Claude
```
BEM-699 | CLAUDE REVIEW | MULTI-AGENT SYSTEM PROTOCOL v2
Date: YYYY-MM-DD | HH:MM (UTC+3)
Decision: APPROVED / CHANGE_REQUIRED / BLOCKED
Accepted points: ...
Required changes: ...
Blocking criteria: ...
Final recommendation: ...
```

No issue comments.
