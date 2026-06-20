# AGENT_CONTEXT.md | canonical operating context

Updated: 2026-06-20
Repository: bereznyi-aleksandr/ai-devops-system
Canonical path: `/AGENT_CONTEXT.md`
Redirect-only companion: `governance/AGENT_CONTEXT.md`

## Startup rule

Read this file first, then `governance/roadmap/ACTIVE_QUEUE.json`, then the protocol and evidence paths referenced by the active task. The root path above is the sole complete agent context. `governance/AGENT_CONTEXT.md` is intentionally redirect-only and must not be expanded into a second full copy.

## Active protocol state

Protocol: BEM-948
Roadmap state: 1/5 stages verified
Current task: `BEM948-P1-AGENT-CONTEXT-SYNC`
Release status: blocked pending P1–P4 verification

P0 `BEM948-P0-REAL-DISPATCH-BRIDGE` is DONE only for the planned-to-executed bridge. Its canonical final receipt is `governance/proofs/BEM948_p0_final_verification_receipt.json` (blob SHA `bc1ce9719d872d840281c47b6c056fc02c83fb5a`, `git_blob`) and its completion commit is `3bf9f8e257cd113ed4436d966ebbf2b2ea7b859bd` (`commit`).

P0 proves the trace-bound chain:
`object_runner -> dispatch_consumer -> dispatch_executor -> claude.yml -> completed Claude report`.

A contradictory task-created completion claim is quarantined by `governance/proofs/BEM948_p0_transport_truth_invalidation_receipt.json`. A terminal trace-matched report in `governance/reports/<trace_id>.md` is stronger evidence than a task-created proof whenever they disagree.

P1 was previously stopped after the retry ceiling for the old blocker. The operator supplied a new, concrete blocker hypothesis: two divergent full `AGENT_CONTEXT.md` files. This canonicalization action resolves that ambiguity by making the root file authoritative and the governance path redirect-only. Do not mark P1 DONE until its remaining acceptance criteria have current task-specific evidence.

P2 verifies runtime enforcement of RULE-004 through RULE-012; RULE-011 and RULE-012 require real enforcement runners, not documentation alone.
P3 is a live `gpt_codex_cloud` failover test through `dispatch_executor.py`; evidence must distinguish actual operation, mechanical fallback, and absence of `OPENAI_API_KEY`.
P4 is final protocol verification and must update this canonical context as part of its acceptance.

## Evidence rules

1. Every SHA recorded in a proof or receipt must declare `sha_type`: `git_blob`, `commit`, or `sha256_content`.
2. `PASS` requires trace-bound `executed` or terminal `completed` evidence. HTTP 204 means dispatched only; `planned` is not executed.
3. Treat unverified causes as hypotheses, not facts.
4. Preserve failed attempts, blockers, and quarantined evidence; never rewrite history to conceal them.
5. For each `task_id` plus named blocker, count only outcome-changing attempts: a code/config change followed by verification, or a new dispatch followed by verification. Passive reading does not reset the counter.
6. After three unsuccessful attempts for the same blocker, set `BLOCKED_OPERATOR_DECISION` and stop retries for that blocker. Resume only with new operator input, an explicitly changed hypothesis, or an instruction to close or roll back.
7. Do not infer workflow success from a dispatch acknowledgement. Read the receipt and the trace-matched terminal report.

## Provider topology

Primary provider for curator, analyst, auditor, and executor: `claude_code`.
Primary workflow: `.github/workflows/claude.yml`.

Configured fallback: `gpt_codex_cloud` on GitHub-hosted infrastructure. It may claim an OpenAI Responses execution only when its runtime secrets are configured; otherwise it must identify itself as a mechanical fallback. Self-hosted `gpt_codex` is disabled and deprecated.

Operational ingress:
`Telegram -> Cloudflare Worker -> provider-router.yml -> claude.yml`.

## Canonical state and evidence paths

- Roadmap: `governance/roadmap/ACTIVE_QUEUE.json`
- Planned dispatches: `governance/state/dispatch_processed.jsonl`
- Dispatch acknowledgements: `governance/state/dispatch_executed.jsonl`
- Terminal role reports: `governance/reports/<trace_id>.md`
- Proofs and receipts: `governance/proofs/`
- Execution history: `governance/logs/execution_log.jsonl`
- Provider policy: `governance/config/provider_config.json 
- Role order policy: `governance/policies/role_sequence.json`
- Routing state: `governance/state/routing.json`

## Integrity boundary

Historical BEM-934 materialization artifacts are outside BEM-948 P0 bridge acceptance. BEM-948 can advance only on current, task-specific, trace-bound evidence with explicit SHA types.
