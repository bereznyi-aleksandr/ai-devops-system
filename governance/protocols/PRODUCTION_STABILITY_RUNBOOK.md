# BEM-526 | Production Stability Runbook

Дата: 2026-05-17 | 11:52 (UTC+3)

## Назначение
Правила восстановления production-контура ai-devops-system без issue #31, без schedule triggers и без платного OpenAI API.

## Активная архитектура
- Executor: GitHub-hosted ubuntu-latest.
- Runtime: Python executor v3.
- Write channel: Deno createCodexTask.
- Status channel: Deno getCodexStatus.
- Paid OpenAI API: disabled.
- Codex CLI: disabled.

## Контракт реакции на сбои
1. queued: ждать и повторить status check ограниченно, не выдавать оператору промежуточный отчёт.
2. completed + commit_sha: блок закрыт.
3. failed + blocker: читать blocker, исправлять одним автономным блоком.
4. result missing после ожидания: проверить GitHub Actions/runner состояние через доступный канал, без issue comments.
5. Python executor ограничение: использовать Run script с доступными globals Path/json/now/changed_files/ops_applied и без import.
6. Невыполнимое через executor: фиксировать blocker и direct-patch request, но не заявлять PASS.

## Запреты
- No issue #31 comments.
- No schedule triggers.
- No secrets in files.
- No paid OpenAI API.
- No Codex CLI until separate approval.

## PASS для P10
- baseline audit exists.
- recovery runbook exists.
- executor Run script verified.
- roadmap can advance to P11.
