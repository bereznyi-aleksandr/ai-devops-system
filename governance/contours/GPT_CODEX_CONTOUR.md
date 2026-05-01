# GPT/CODEX CONTOUR — Резервный контур
Версия: v1.0 | Дата: 2026-05-01

## Описание
Резервный контур. Активируется только при недоступности Claude Code и только после owner approval.

## Роли и триггеры

| Роль | Триггер | Механизм |
|---|---|---|
| GPT_ANALYST | @codex ROLE=GPT_ANALYST | ручной / GPT |
| GPT_AUDITOR | @codex ROLE=GPT_AUDITOR | ручной / GPT |
| GPT_EXECUTOR | @codex ROLE=GPT_EXECUTOR | ручной / GPT |

## Цепочка

```
@codex ROLE=GPT_ANALYST → анализирует
→ @codex ROLE=GPT_AUDITOR → проверяет
→ @codex ROLE=GPT_EXECUTOR → создаёт draft PR (не коммитит в main)
→ Owner review → merge только владелец
```

## Промпты

- governance/prompts/gpt_analyst_prompt.md
- governance/prompts/gpt_auditor_prompt.md
- governance/prompts/gpt_executor_prompt.md

## Ограничения GPT_EXECUTOR

- Только отдельная ветка
- Только draft PR
- Никаких прямых коммитов в main
- Никакого merge
- Никаких изменений secrets/billing/permissions
- Никакого production deploy

## Условия активации

1. Только при предложении GPT-куратора
2. Только после явного owner approval
3. Фиксируется в EXCHANGE.md и exchange.jsonl
