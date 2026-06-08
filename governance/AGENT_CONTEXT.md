# AGENT_CONTEXT.md | canonical configuration

Updated: 2026-06-08
Repository: bereznyi-aleksandr/ai-devops-system
Instruction version: 2.9
Protocol status: BEM-931 v3.6 active
System status: WORKING_CONTOUR_NOT_READY

## ПЕРВОЕ ДЕЙСТВИЕ ПРИ СТАРТЕ СЕССИИ

1. Читать `SYSTEM_STATUS.md` в корне репо — там концепция, что сделано, что осталось
2. Читать `governance/roadmap/ACTIVE_QUEUE.json` — текущие задачи
3. Взять первую IN_PROGRESS или PENDING задачу и выполнять

## Role

GPT is an external autonomous implementation agent for the repository.
Claude is peer external auditor.
Operator is strategic authority only, not a relay between tasks.

## Canonical runtime

Canonical LLM runtime: `.github/workflows/codex-local.yml`
Provider: GPT Codex via ChatGPT Plus subscription (OAuth, not API key)
Runner: self-hosted runner with Codex CLI and OAuth session.
Curator runtime must use Codex Local only.

Forbidden active production runtimes:
- Gemini API
- OpenAI HTTP API (OPENAI_API_KEY)
- paid hosted GPT runtime
- `.github/workflows/gpt-hosted-roles.yml` as active curator runtime

`gpt-hosted-roles.yml` exists only as archived/disabled stub.

## System architecture (summary)

Full architecture: see `SYSTEM_STATUS.md` section 1.

Objects: GD → DIR → WRK
Each WRK has: WRK.CURATOR + WRK-C1, WRK-C2, WRK-C3 (minimum)
Each WRK-Cx has: ANALYST → AUDITOR.pre → EXECUTOR → AUDITOR.post
All roles run via Codex CLI (codex exec) with AGENTS.md instructions.

## What is done / what remains

See `SYSTEM_STATUS.md` sections 2 and 3.

Critical gaps blocking production:
1. AGENTS.md missing — Codex has no system instructions
2. Roles not connected to Codex via orchestrator (run as Python stubs without LLM)
3. Provider system missing (no GPT↔Claude fallback)
4. Telegram E2E not proven with live receipt

## Current tasks

`governance/roadmap/ACTIVE_QUEUE.json` — execute only from here.
`SYSTEM_STATUS.md` — update after each completed stage.

Task closure requires:
- non-null commit SHA
- result artifact
- validator or receipt
- execution log entry
- canonical operator report when required

Documentation-only closure is NOT valid for runtime tasks.

## Report canon

Operator report (Telegram):
- stage progress: X/Y tasks (%)
- roadmap progress: X/Y stages (%)
- checklist as separate lines with ✅ / ❌
- operator question only if required

Forbidden: diff, stdout, stderr, traceback, raw JSON, reasoning text.

## File roles

`SYSTEM_STATUS.md` — ГЛАВНЫЙ ДОКУМЕНТ: концепция, статус, дорожная карта
`governance/roadmap/ACTIVE_QUEUE.json` — current executable queue
`governance/logs/execution_log.jsonl` — append-only history
`governance/reports/operator/` — canonical operator reports
`governance/proofs/` — receipts and proof artifacts
`governance/protocols/bem931_v3_6_working_contour_detailed_roadmap.md` — detailed protocol
