# SCHEDULER PROTOCOL — AI DevOps System
Версия: v1.0 | Дата: 2026-05-02

## НАЗНАЧЕНИЕ

Два независимых scheduler для двух кураторов системы.
Каждый scheduler работает со своей очередью и не трогает очередь другого.

## АРХИТЕКТУРА

```
GPT-КУРАТОР              CLOUD-КУРАТОР
     |                        |
gpt_scheduler_tick.py   cloud_scheduler_tick.py
     |                        |
schedulers/gpt/         schedulers/cloud/
  queue.json              queue.json
  state.json              state.json
  reports/                reports/
     |                        |
     +--------+--------+
              |
    governance/exchange.jsonl  (общий state layer)
    governance/EXCHANGE.md
    governance/MASTER_PLAN.md
```

## РОЛИ

### GPT-КУРАТОР
- Архитектура, контроль, BEM-отчётность
- Резервный GPT/Codex контур
- Очередь: `governance/schedulers/gpt/`

### CLOUD-КУРАТОР
- Кодовое исполнение
- Основной Claude Code executor контур
- Очередь: `governance/schedulers/cloud/`

## ПРАВИЛА

### Независимость очередей
1. GPT scheduler читает только `schedulers/gpt/queue.json`
2. Cloud scheduler читает только `schedulers/cloud/queue.json`
3. Один scheduler НЕ исполняет задачи другого
4. Один scheduler НЕ записывает в очередь другого

### One-step-per-tick
Каждый tick обрабатывает только одну задачу из своей очереди.
Следующая задача — следующий tick.

### Статусы задач
| Статус | Описание |
|---|---|
| pending | Задача ожидает выполнения |
| running | Задача выполняется в текущем tick |
| done | Задача успешно завершена |
| blocked | Задача заблокирована, требует внимания |

### Отчёт после задачи
После каждой закрытой задачи (done/blocked):
1. Создать отчёт в `schedulers/{scheduler}/reports/BEM-XXX-{task_id}.md`
2. Обновить `state.json`
3. Добавить событие в `governance/exchange.jsonl`
4. Опубликовать короткий BEM-отчёт в issue #31

### Формат события в exchange.jsonl
```json
{
  "timestamp": "...",
  "source": "gpt_scheduler / cloud_scheduler",
  "event_type": "GPT_SCHEDULER_TICK / CLOUD_SCHEDULER_TICK",
  "task_id": "...",
  "status": "done / blocked",
  "next_action": "..."
}
```

### Что владелец получает
Только короткие BEM-отчёты в issue #31.
Детали — в `schedulers/{scheduler}/reports/`.

## ОБЩИЙ STATE LAYER
- `governance/EXCHANGE.md` — текущее состояние ISA
- `governance/exchange.jsonl` — журнал всех событий
- `governance/MASTER_PLAN.md` — дорожная карта

## ЗАПРЕЩЕНО
- Смешивать GPT и Claude execution внутри одного tick
- Трогать secrets/billing/permissions/production/auto-merge
- Удалять archive/quarantine
- Ломать текущий codex-local.yml
