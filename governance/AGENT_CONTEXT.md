# AGENT_CONTEXT.md | canonical operating context

Updated: 2026-06-20
Repository: bereznyi-aleksandr/ai-devops-system
Active protocol: BEM-948
Roadmap state: 1/5 stages verified
Current task: BEM948-P1-AGENT-CONTEXT-SYNC
Release status: BLOCKED_BUILDING

## Autonomous execution contract

1. Read `governance/AGENT_CONTEXT.md` and `governance/roadmap/ACTIVE_QUEUE.json`.
2. Take the first `IN_PROGRESS` task; otherwise take the first `PENDING` task.
3. Execute, verify external evidence, update queue and `governance/logs/execution_log.jsonl`, then continue immediately to the next roadmap task.
4. Do not claim PASS from a dispatch acknowledgement. HTTP 204 means `dispatched` only.
5. For a Claude-dispatched task, the terminal trace-matched report in `governance/reports/<trace_id>.md` determines the role outcome. A task-created proof may not override a terminal workflow failure.
6. When evidence conflicts, quarantine the weaker claim and preserve both records with explicit SHA types.

## Verified BEM-948 state

P0 `BEM948-P0-REAL-DISPATCH-BRIDGE` is DONE for the planned-to-executed bridge only.

Canonical P0 final receipt:
- `governance/proofs/BEM948_p0_final_verification_receipt.json`
- blob SHA: `bc1ce9719d872d840281c47b6c056fc02c83fb5a` (`git_blob`)
- completion commit: `3bf9f8e257cd113ed4436d966ebf2b2ea7b859bd` (`commit`)

P0 proves a trace-bound chain:
`object_runner -> dispatch_consumer -> dispatch_executor -> claude.yml -> completed Claude report`.

P0 also has explicit reconciliation evidence:
- `governance/proofs/BEM948_p0_final_bridge_reconciliation_receipt.json`
- `governance/proofs/BEM948_p0_transport_truth_invalidation_receipt.json`

The invalidation receipt quarantines a contradictory task-created completed claim when the terminal Claude transport report recorded `claude_role outcome=failure`. Do not reuse quarantined evidence as a PASS source.

P1 synchronizes this document. P2 verifies enforcement of real rules. P3 tests `gpt_codex_cloud` failover. P4 performs final verification. None of P2-P4 is verified yet.

## Provider topology

Primary provider for curator, analyst, auditor, and executor: `claude_code`.
Primary workflow: `.github/workflows/claude.yml`.

Configured fallback: `gpt_codex_cloud`, GitHub-hosted reserve path.
It may use OpenAI Responses only when its runtime secrets are configured; otherwise it must identify itself as a mechanical fallback. `gpt_codex` self-hosted is disabled and deprecated.

Operational ingress remains:
`Telegram -> Cloudflare Worker -> provider-router.yml -> claude.yml`.

## Canonical state and evidence

- Roadmap: `governance/roadmap/ACTIVE_QUEUE.json`
- Planned dispatches: `governance/state/dispatch_processed.jsonl`
- Dispatch acknowledgements: `governance/state/dispatch_executed.jsonl`
- Terminal role reports: `governance/reports/<trace_id>.md`
- Proofs: `governance/proofs/`
- Execution history: `governance/logs/execution_log.jsonl`
- Provider policy: `governance/config/provider_config.json`
- Role order policy: `governance/policies/role_sequence.json`
- Routing state: `governance/state/routing.json`

## Integrity boundary

Historical BEM-934 materialization artifacts remain outside the BEM-948 P0 bridge acceptance scope. Do not use them to assert a broader release PASS. BEM-948 can advance only on current task-specific, trace-bound evidence with explicit SHA types.
