# AGENT_CONTEXT.md | canonical operating context

Updated: 2026-06-20
Repository: bereznyi-aleksandr/ai-devops-system
Canonical path: `/AGENT_CONTEXT.md`
Redirect-only companion: `governance/AGENT_CONTEXT.md`

## Startup rule

Read this file first, then `governance/roadmap/ACTIVE_QUEUE.json`, then the protocol and evidence paths referenced by the active task. The root path above is the sole full agent context. `governance/AGENT_CONTEXT.md` is intentionally redirect-only and must not be expanded into a second full copy.

## BEM-948 final verified state

Protocol: BEM-948
Roadmap state: 5/5 stages verified
Current task: none
Release status: VERIFIED_WITH_LIMITATIONS
Final verification receipt: `governance/proofs/BEM948_p4_final_verification_receipt.json`

- P0 `BEM948-P0-REAL-DISPATCH-BRIDGE` is DONE for the trace-bound planned-to-executed bridge only. Canonical receipt: `governance/proofs/BEM948_p0_final_verification_receipt.json` (blob `bc1ce9719d872d840281c47b6c056fc02c83fb5a`, `git_blob`); completion commit `3bf9f8e257cd113ed4436d956ebbf2b2ea7b859bd` (`commit`).
- P1 `BEM948-P1-AGENT-CONTEXT-SYNC` is DONE. Root context is canonical; the governance path is redirect-only. Final receipt: `governance/proofs/BEM948_p1_final_verification_receipt.json` (blob `4474b042a8d3ae3e5ea55ccbac55bd12f6c27b96`, `git_blob`); commit `046300603df0ee82534319a12ede564722094d1f` (`commit`).
- P2 `BEM948-P2-RULE-ENFORCEMENT-VERIFICATION` is DONE within its recorded scope. RULE-011 evidence and RULE-012 continuity have runtime enforcers; RULE-004 through RULE-010 remain explicitly `NOT_VERIFIED a, not enforced by implication. The action reached enforcement but failed while persisting its receipt; the reconciled receipt preserves that workflow failure.
- P3 `BEM948-P3-PROVIDER-FAILOVER-LIVE-TEST` is DONE as a trace-bound GitHub-hosted mechanical fallback. The terminal provider receipt records `llm_available=false` and an OpenAI secret/model mismatch. Do not describe it as an OpenAI Responses API or LLM execution.
- P4 `BEM948-P4-FINAL-VERIFY` verified the recorded state and preserved all scope limitations. `VERIFIEG_WITH_LIMITATIONS` is not a broader release PASS.

## Evidence rules

1. Every SHA in a proof or receipt must carry `sha_type`: `git_blob`, `commit`, or `sha256_content`.
2. A runtime `PASS` requires trace-bound `executed` evidence or a terminal `completed` report. HTTP 204 means dispatched only; planned means not executed.
3. A terminal trace-matched report or provider receipt is stronger than a task-created proof when they conflict.
4. Preserve failed attempts, blockers, reconciliation records, and quarantined evidence.
5. Count outcome-changing attempts per task and named blocker. After three unsuccessful attempts, set `BLOCKED_OPERATOR_DECISION` and resume only on new operator input, a changed hypothesis, or an explicit close/rollback instruction.
6. Do not infer causes without an API response, parser result, log, or equivalent observable evidence.

## Verified limitations and operator decisions

- RULE-004 through RULE-010 need separate code-backed enforcement work before any claim that the full RULE-004..012 set is enforced.
- `gpt_codex_cloud` was validated only as a GitHub-hosted mechanical fallback; it did not establish a live OpenAI LLM call because the terminal receipt reports no usable OpenAI secret/model pair.
- The historical `governance/logs/execution_log.jsonl` formatting remains a legacy integrity limitation; do not claim that BEM-948 entries were appended until a separately verified repair records them.
- The P2 workflow terminal failure at receipt persistence remains historical evidence; the reconciled receipt does not convert it into a workflow-success claim.

## Provider topology

Primary provider for curator, analyst, auditor, and executor: `claude_code`.
Primary workflow: `.github/workflows/claude.yml`.

Configured fallback: `gpt_codex_cloud` on GitHub-hosted infrastructure. It may claim OpenAI Responses execution only when runtime secrets and a model are configured; otherwise it must identify itself as a mechanical fallback.
Operational ingress: `Telegram -> Cloudflare Worker -> provider-router.yml -> claude.yml`.

## Canonical state and evidence paths

- Roadmap: `governance/roadmap/ACTIVE_QUEUE.json`
- Planned dispatches: `governance/state/dispatch_processed.jsonl`
- Dispatch acknowledgements: `governance/state/dispatch_executed.jsonl`
- Terminal role reports: `governance/reports/<trace_id>.md`
- Proofs and receipts: `governance/proofs/`
- Exection history: `governance/logs/execution_log.jsonl`
- Provider policy: `governance/config/provider_config.json`
- Role order policy: `governance/policies/role_sequence.json`
- Routing state: `governance/state/routing.json

## Integrity boundary

Historical BEM-934 materialization artifacts remain outside BEM-948 acceptance scope. BEM-948 may be treated only as `VERIFIEG_WITH_LIMITATIONS`, based on current task-specific, trace-bound evidence with explicit SHA types.
