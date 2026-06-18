# AGENT_CONTEXT.md | canonical startup context

Updated: 2026-06-18T17:40:00Z
Repository: bereznyi-aleksandr/ai-devops-system

## Startup rule

Read this file first, then `governance/roadmap/ACTIVE_QUEUE.json`, then the current protocol referenced by that queue.

## Current verified state

BEM-934 is closed: roadmap 10/10, `ACTIVE_QUEUE` COMPLETE, release PASS.
Canonical evidence:
- `governance/proofs/BEM934_live_test_receipt.json`
- `governance/proofs/BEM934_external_auditor_verdict.json`
- `governance/proofs/BEM934_external_audit_run_receipt.json`
- `governance/proofs/BEM934_close_receipt.json`
- `governance/proofs/BEM934_FINAL_VERIFICATION_PASS.json`

## Runtime reality

The proven operational route is:

`Operator Telegram -> Cloudflare Worker -> provider-router workflow -> claude.yml -> anthropics/claude-code-action@v1 -> report/proof commit`.

Primary provider for curator, analyst, auditor, and executor is `claude_code`.
Self-hosted Codex is disabled, deprecated, and non-operational.
`gpt_codex_cloud` is reserve only; without OpenAI runtime secrets it is mechanical fallback, not an LLM execution claim.

## Next modernization track

BEM-935 starts from the external audit findings after BEM-934:
- replace critical 23-byte Python stubs with runtime code,
- process dispatch queue into `dispatch_processed.jsonl`,
- keep root context present for new sessions,
- avoid claiming multi-provider autonomy until router, consumer, failover, event logging, and Telegram input handling are implemented and proof-tested.
