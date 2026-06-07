# BEM-931 | Архив платных и устаревших runtime-веток

Updated: 2026-06-07
Status: archived policy

## Решение

Куратор больше не должен работать через платные HTTP API ветки:

- Gemini API;
- OpenAI HTTP API через `gpt-hosted-roles.yml`;
- любые hosted role ветки, которые требуют отдельной оплаты за вызовы API.

Канонический runtime куратора:

```text
codex-local.yml
self-hosted runner
Codex CLI
ChatGPT OAuth / GPT Plus
```

## Что сделано

- `telegram-poll.yml` переключён на `codex-local.yml`.
- `operator-hourly-curator-report.yml` переключён на `codex-local.yml`.
- `gpt-hosted-roles.yml` превращён в disabled stub и не вызывает Gemini/OpenAI API.
- Для curator в `codex-local.yml` добавлен вывод в `governance/telegram_outbox.jsonl`.

## Дальнейшая задача

Заархивировать и проверить все оставшиеся неактуальные workflow/ветки, которые используют:

- Gemini;
- OpenAI HTTP API;
- hosted paid LLM runtime;
- mock/skeleton PASS без реального E2E.

Архивация означает:

1. workflow не должен запускаться автоматически;
2. workflow не должен мешать каноническому runtime;
3. workflow должен иметь явный статус ARCHIVED/DEPRECATED;
4. если workflow нужен для аварийного восстановления, это должно быть явно написано.
