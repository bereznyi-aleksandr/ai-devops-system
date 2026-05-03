# EXCHANGE — AI DevOps System ISA State
Версия: v2.0 | Дата: 2026-05-03

---

## ROUTING TABLE — ТЕКУЩАЯ КОНФИГУРАЦИЯ РОЛЕЙ

| Роль | Реализация | Триггер |
|---|---|---|
| ANALYST | claude | @analyst |
| AUDITOR | claude | @auditor |
| EXECUTOR | claude | @executor |

Допустимые реализации: `claude` / `gpt`

Переключение из Telegram:
- `аналитик gpt` → ANALYST = gpt → триггер @codex ROLE=GPT_ANALYST
- `аналитик claude` → ANALYST = claude → триггер @analyst
- `аудитор gpt` → AUDITOR = gpt → триггер @codex ROLE=GPT_AUDITOR
- `аудитор claude` → AUDITOR = claude → триггер @auditor
- `исполнитель gpt` → EXECUTOR = gpt → триггер @codex ROLE=GPT_EXECUTOR
- `исполнитель claude` → EXECUTOR = claude → триггер @executor

---

## ТЕКУЩЕЕ СОСТОЯНИЕ

| Параметр | Значение |
|---|---|
| repository | bereznyi-aleksandr/ai-devops-system |
| main_issue | #31 |
| current_phase | E3 — первый автономный цикл |
| active_contour | mixed (настраивается per role) |

---

## ЦЕПОЧКА ВЫПОЛНЕНИЯ

```
ANALYST (claude/gpt) → анализирует → передаёт AUDITOR
AUDITOR (claude/gpt) → проверяет → APPROVED → передаёт EXECUTOR
EXECUTOR (claude/gpt) → выполняет → AUDITOR VERIFY
```

---

## ПРИМЕРЫ КОМБИНАЦИЙ

| Конфигурация | Когда использовать |
|---|---|
| Claude + Claude + Claude | Штатный режим |
| GPT + Claude + Claude | Claude Code на лимите для анализа |
| Claude + Claude + GPT | Claude Code на лимите для исполнения |
| GPT + GPT + GPT | Claude Code полностью недоступен |

---

## ПОСЛЕДНИЕ СОБЫТИЯ
| Дата | Событие |
|---|---|
| 2026-05-03 | Система перезапущена — куратор удалён из схемы |
| 2026-05-03 | Telegram gateway создан |
| 2026-05-03 | Routing table инициализирована — все роли на claude |
