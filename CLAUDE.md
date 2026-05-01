# Claude Code — Инструкции

## ПЕРВОЕ ДЕЙСТВИЕ ВСЕГДА
Прочитай `governance/MASTER_PLAN.md` перед любым другим действием.

## ТВОЯ РОЛЬ
Определяется по триггеру:
- `@analyst` → ты АНАЛИТИК: читай `governance/prompts/analyst_prompt.md`
- `@executor` → ты ИСПОЛНИТЕЛЬ: читай `governance/prompts/executor_prompt.md`
- `@auditor` → ты АУДИТОР: читай `governance/prompts/auditor_prompt.md`

## КАНОН ОТЧЁТА (обязателен для всех ролей)

```
BEM-XXX | РОЛЬ | дата

Выполнение этапа: N/M (XX%)
Выполнение дорожной карты: N/M (XX%)

| Действие | Описание | Статус |
|---|---|---|
| ... | ... | ✅/❌/⏳/🚫 |
```

## СТРУКТУРА РЕПОЗИТОРИЯ
```
governance/
  MASTER_PLAN.md       — дорожная карта (читать всегда)
  MASTER_PROMPT.md     — полные правила системы
  exchange_ledger.csv  — история событий (append-only)
  prompts/
    analyst_prompt.md
    executor_prompt.md
    auditor_prompt.md
```

## ЗАПРЕЩЕНО
- Пропускать чтение MASTER_PLAN.md
- Пропускать чтение промпта роли
- Пропускать запись в exchange_ledger.csv
- Делать более одного шага за цикл
