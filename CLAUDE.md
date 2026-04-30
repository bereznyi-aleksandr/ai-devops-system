# Claude Code — Инструкции для всех ролей

## ОПРЕДЕЛЕНИЕ РОЛИ

Твоя роль определяется командой в issue/комментарии:

- Если запущен как `executor` job → ты ИСПОЛНИТЕЛЬ
- Если запущен как `analyst` job → ты АНАЛИТИК  
- Если запущен как `auditor` job → ты АУДИТОР
- Иначе → общий режим

Перед любым действием прочитай промпт своей роли:
- ИСПОЛНИТЕЛЬ: `governance/prompts/executor_prompt.md`
- АНАЛИТИК: `governance/prompts/analyst_prompt.md`
- АУДИТОР: `governance/prompts/auditor_prompt.md`

## ПЕРВОЕ ДЕЙСТВИЕ ВСЕГДА

1. Прочитать `governance/MASTER_PLAN.md`
2. Прочитать промпт своей роли из `governance/prompts/`
3. Прочитать последние 5 строк `governance/exchange_ledger.csv`
4. Выполнить задачу из issue

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
    executor_prompt.md — инструкции ИСПОЛНИТЕЛЯ
    analyst_prompt.md  — инструкции АНАЛИТИКА
    auditor_prompt.md  — инструкции АУДИТОРА
```

## ЗАПРЕЩЕНО ВСЕГДА

- Пропускать чтение MASTER_PLAN.md
- Пропускать чтение промпта роли
- Пропускать запись в exchange_ledger.csv
- Делать более одного шага за цикл
