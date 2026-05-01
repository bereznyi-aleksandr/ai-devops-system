# CLAUDE CONTOUR — Основной контур
Версия: v1.0 | Дата: 2026-05-01

## Описание
Основной контур системы. Использует Claude Code через GitHub Actions.

## Роли и триггеры

| Роль | Триггер | Workflow |
|---|---|---|
| АНАЛИТИК | @analyst | analyst.yml |
| АУДИТОР | @auditor | auditor.yml |
| ИСПОЛНИТЕЛЬ | @executor | executor.yml |
| Общий | @claude | claude.yml |

## Цепочка

```
@analyst → АНАЛИТИК анализирует → @auditor REVIEW
@auditor → проверяет → @executor EXECUTE (если APPROVED)
           или → @analyst REVISION (если BLOCKED)
@executor → выполняет → @auditor VERIFY
@auditor → APPROVED → задача закрыта
```

## Промпты

- governance/prompts/analyst_prompt.md
- governance/prompts/auditor_prompt.md
- governance/prompts/executor_prompt.md

## Условия переключения на fallback

Только при явном owner approval после предложения куратора:
1. Claude Code usage limit reached
2. Claude Code Action temporarily unavailable
3. Primary contour завис более одного часового цикла
