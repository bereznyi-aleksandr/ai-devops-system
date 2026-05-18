# BEM-608 | Claude Primary Provider Gate

Дата: 2026-05-18 | 06:15 (UTC+3)

## Назначение

Перед исполнением задач внутреннего контура нужно зафиксировать, доступен ли основной Claude provider, или нужно уходить в GPT reserve.

## Что проверяется без раскрытия секретов
- наличие `CLAUDE_CODE_OAUTH_TOKEN`
- наличие `ANTHROPIC_API_KEY`
- наличие workflow окружения GitHub Actions

## Ограничение
Проверка наличия секрета не доказывает фактический runtime Claude Code и лимиты. Если нужен строгий PASS, должен быть отдельный Claude smoke/action, создающий ответ в repo.
