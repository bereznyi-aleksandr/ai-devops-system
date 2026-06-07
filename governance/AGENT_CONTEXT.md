# AGENT_CONTEXT.md | canonical configuration

Updated: 2026-06-07
Repository: bereznyi-aleksandr/ai-devops-system
Instruction version: 2.8
Protocol status: BEM-931 v3.6 active
System status: WORKING_CONTOUR_NOT_READY

## Role

GPT is an external auditor and implementation agent for the repository.
Claude is peer external auditor.
Operator is strategic authority only, not a relay between tasks.

## Canonical runtime

Canonical LLM runtime: `.github/workflows/codex-local.yml`
Provider: `codex_local`
Runner: self-hosted runner with Codex CLI and OAuth session.
Curator runtime must use Codex Local only.

Forbidden active production runtimes:
- Gemini API
- OpenAI HTTP API
- paid hosted GPT runtime
- `.github/workflows/gpt-hosted-roles.yml` as active curator runtime

`gpt-hosted-roles.yml` may exist only as archived/disabled stub and must not call any API.

## Current status

The managing contour is not production-ready.
Do not report "working contour complete" until all live receipts are present.

Required for release:
- canonical objects: GD, DIR, WRK
- canonical contours: GD-C1, GD-C2, DIR-C1, DIR-C2, WRK-C1, WRK-C2, WRK-C3
- each internal contour has ANALYST, AUDITOR, EXECUTOR
- curators exist as runtime elements: GD.CURATOR, DIR.CURATOR, WRK.CURATOR
- every element has prompt_profile_id and provider_binding_id
- Codex Local provider receipt exists for every live role execution
- managed channels route operator -> GD -> DIR -> WRK -> WRK-Cx and back
- live E2E trace exists
- Telegram receipt exists
- external Claude audit receipt exists
- legacy Gemini/API/paid hosted paths are disabled or archived

## Startup protocol

1. Read this file.
2. Read `governance/roadmap/ACTIVQUEUE.json`.
3. Take the first task with status `IN_PROGRESS` or `PENDING`.
4. Execute only from ACTIVE_QUEUE. Do not invent tasks.
5. A task may be marked DONE only when it has:
   - non-null commit SHA
   - result artifact path
   - validator or receipt
   - execution log entry
   - canonical operator report when required
6. Documentation-only closure is not valid for runtime tasks.
7. Continue to the next pending task only when acceptance evidence exists.

## File roles

`governance/protocols/bem931_v3_6_working_contour_detailed_roadmap.md` — source protocol for working contour implementation.
`governance/roadmap/ACTIVE_QUEUE.json` — current executable queue.
`governance/logs/execution_log.jsonl` — append-only history.
`governance/reports/operator/` — canonical operator reports.
`governance/proofs/` — receipts and proof artifacts.
`governance/traces/` — runtime traces.

## Evidence rules

PASS requires non-null SHA from GitHub create/update response.
Proof-only commits are not release evidence.
Live runtime requires provider receipt, trace, and accepted result.
No secrets or tokens in repository files.
No raw logs, stdout, stderr, diffs, or tracebacks in Telegram operator reports.

## Report canon

Operator report must contain only:
- stage progress: tasks inside current stage
- roadmap progress: stages completed
- checklist as separate lines
- operator question only if required
- for direct answers: short answer + next step

## Current source of tasks

Use `ACTIVE_QUEUE.json` only.
Current queue is seeded from BEM-931 v3.6 with priority:
1. RM-01 — working contour status/gap reset
2. RM-14 — legacy runtime archive
