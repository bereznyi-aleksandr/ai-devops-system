# BEM-531.01 | Curator Intake Contract

Дата: 2026-05-17 | 14:01 (UTC+3)

## Архитектурное правило
Внешний контур не управляет внутренними workflow напрямую. Единственная точка входа во внутренний контур — curator.

## Внешние источники
- GPT Custom GPT
- Claude external auditor
- Telegram bot/webhook

Все источники создают задачу для curator. Дальше curator сам определяет роль и внутренний маршрут.

## Формат входящей задачи куратору
```json
{
  "trace_id": "string",
  "source": "gpt | claude | telegram",
  "task_type": "development | audit | hotfix",
  "title": "string",
  "objective": "string",
  "created_at": "ISO-8601 or YYYY-MM-DD | HH:MM (UTC+3)",
  "blocker": null
}
```

## Правила curator routing
| Условие | Следующая роль | Обоснование |
|---|---|---|
| Новая задача разработки | analyst | Требуется анализ решения |
| Задача аудита | auditor | Требуется проверка без patch |
| Срочный hotfix с понятным patch | auditor -> executor | Patch должен пройти аудит перед исполнением |
| Claude failed/cancelled/timeout | provider-adapter -> GPT reserve | Failover policy BEM-535 |
| Любой blocker | curator | Куратор закрывает/переназначает цикл |

## Как curator запускает внутренний контур
1. Читает задачу из `governance/tasks/pending/` или transport intake record.
2. Валидирует schema.
3. Обновляет `governance/state/role_cycle_state.json`.
4. Пишет intake/handoff record в `governance/transport/results.jsonl`.
5. Назначает analyst/auditor/executor.
6. При необходимости запускает внутренние workflows через разрешённый внутренний механизм.
7. Получает результат роли.
8. Закрывает цикл final_result record.
9. Возвращает результат внешнему контуру через файл отчёта/state/transport.

## Как curator возвращает результат GPT
Curator пишет:
- `governance/transport/results.jsonl` final_result;
- `governance/state/role_cycle_state.json` с `curator_status=CLOSED`;
- report в `governance/reports/`;
- blocker=null или точный blocker object.

GPT читает только эти файлы и не управляет internal workflows напрямую.

## Запреты
- External GPT/Claude/Telegram не dispatch internal workflows напрямую.
- No issue #31 comments.
- No secrets in files.
- No paid API by default.
- Schedule policy: only `curator-hourly-report.yml` exception is allowed by contract v1.9.
