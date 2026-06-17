# BEM-934 Protocol — cloud provider migration

Date: 2026-06-16
Repository: bereznyi-aleksandr/ai-devops-system
Source: BEM934_Protocol.docx
Status: APPROVED TO EXECUTE
Operator scope: autonomous execution without stops.

## Core decision

The operator will not deploy a physical self-hosted runner. `codex-local.yml` and
`codex-local-assembled.yml` are therefore historical/deprecated paths. All production
roles use `claude.yml` on GitHub-hosted runners as primary. A GitHub-hosted
`gpt-codex-cloud.yml` is retained as a secondary path: it uses OpenAI API only when
`OPENAI_API_KEY` exists; otherwise it performs a clearly marked mechanical fallback
without claiming LLM reasoning.

## Roadmap

1. `BEM934-CONFIG-SWAP` — set Claude primary and cloud Codex fallback for all roles.
2. `BEM934-DEPRECATE-SELFHOSTED` — mark both self-hosted workflows deprecated and remove active references.
3. `BEM934-GPT-CLOUD-PATH` — create a non-self-hosted cloud workflow that completes without queueing.
4. `BEM934-PROVIDER-CONFIG-UPDATE` — register `gpt_codex_cloud`, disable old `gpt_codex`.
5. `BEM934-ROUTER-RENAME-FIX` — normalize provider state keys and remove synthetic stale state.
6. `BEM934-PROMPT-ASSEMBLER-RECONNECT` — assemble role prompt before Claude execution.
7. `BEM934-STAGE-RUNNER-RECONNECT` — replace fixed plans/size-only audit with provider-backed semantic requests and fail-closed validation.
8. `BEM934-OBJECTS-BOUND` — mark object runtime binding only after a proof-bearing contour test.
9. `BEM934-LIVE-TEST` — content-bearing Telegram E2E through `provider-router.yml -> claude.yml`.
10. `BEM934-CLOSE` — update canonical context/status and obtain external auditor approval.

## Closure criteria

- Claude is primary for curator/analyst/auditor/executor.
- No enabled provider targets self-hosted workflows.
- Prompt assembler materially affects Claude prompts.
- Stage runners no longer emit the historical fixed three-step plan and no longer use
  file-size-only acceptance.
- Object registry is `BOUND` only with trace/SHA evidence.
- Content-bearing live Telegram receipt exists.
- Canonical docs do not present self-hosted/Codex-local as an available runtime.
- External auditor verdict is `APPROVED`.
