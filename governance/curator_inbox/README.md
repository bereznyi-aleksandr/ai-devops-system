# GPT Curator Inbox — README
Версия: v1.0 | Дата: 2026-05-02 | BEM-259

## НАЗНАЧЕНИЕ

Автономный non-UI ingress для GPT-КУРАТОРА.

GPT-КУРАТОР ставит задачи через этот inbox без:
- issue comments (засоряют почту оператора)
- UI popup/confirmation
- прямых GitHub API write-вызовов из ChatGPT connector

## СХЕМА

```
GPT-КУРАТОР
  → пишет задачу в gpt_tasks.jsonl
  → коммитит через repo-native write (без popup)
        ↓
gpt-curator-inbox.yml workflow
  → читает pending tasks из gpt_tasks.jsonl
  → обрабатывает задачу
  → переносит в processed/
  → записывает событие в exchange.jsonl
  → коммитит результат
```

## ФАЙЛЫ

| Файл | Назначение |
|---|---|
| `gpt_tasks.jsonl` | Очередь задач от GPT-куратора |
| `processed/` | Обработанные задачи |
| `../process_gpt_curator_inbox.py` | Обработчик задач |

## ФОРМАТ ЗАДАЧИ

```json
{
  "task_id": "TASK-GPT-XXX",
  "title": "краткое название",
  "status": "pending",
  "created_by": "BEM-XXX",
  "created_at": "ISO timestamp",
  "action": "verify | sync | report | fix",
  "description": "описание",
  "requires_owner_approval": false
}
```

## ПРАВИЛА

1. GPT-КУРАТОР только добавляет задачи — не удаляет
2. Runner обрабатывает одну pending задачу за тик
3. После обработки задача копируется в processed/
4. Все события фиксируются в exchange.jsonl
5. Никаких issue comments из inbox processor
