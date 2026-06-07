# BEM-931 v3.6 — RM-14 Legacy Runtime Archive Report

Статус: DONE_REPO
Дата: 2026-06-07T16:20:00Z

## Проверенные workflow

| Файл | Статус | Вывод |
|---|---|---|
| `.github/workflows/gpt-hosted-roles.yml` | ARCHIVED / disabled stub | Не вызывает Gemini/OpenAI HTTP API. Текст workflow прямо указывает: использовать `codex-local.yml`. |
| `.github/workflows/telegram-poll.yml` | active | Dispatch идёт в `codex-local.yml` с `provider=gpt_codex`; активного `GEMINI_API_KEY` нет. |
| `.github/workflows/codex-local.yml` | canonical active runtime | Self-hosted runner `[self-hosted, codex-local]`; Codex CLI проверяется и запускается через `codex exec`. |
| `.github/workflows/role-orchestrator.yml` | active orchestration | Не содержит Gemini/OpenAI HTTP API runtime. |
| `.github/workflows/telegram-outbox-dispatch.yml` | active Telegram delivery | Только Telegram delivery; LLM provider не вызывает. |

## Результат

✅ `gpt-hosted-roles.yml` подтверждён как архивный disabled stub.  
✅ Штатный curator runtime — `codex-local.yml`.  
✅ Активный Telegram poll dispatch использует `codex-local.yml`, а не `gpt-hosted-roles.yml`.  
✅ Активный Gemini/OpenAI HTTP API curator path не обнаружен в проверенных runtime Workflow.  
✅ RM-14 можно закрыть на repo-level.

## Ограничение

Это repo-level подтверждение по доступным и известным workflow-файлам. Production release всё равно остаётся BLOCKED до live receipts и внешнего Claude audit по release gate RM-18.
