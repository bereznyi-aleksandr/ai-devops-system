# AGENT CONTEXT | CANONICAL START STATE

Updated: 2026-05-25 | 12:48 (UTC+3)

## Purpose
This file is the canonical startup context for GPT and Claude agents. New agent chats must read this file before taking development action.

## Current phase
Roadmap: autonomous multi-agent development contour repair. Current priority: prove reliable GPT to Claude dispatch, Claude runtime state, and real Claude mailbox response.

## Required proof triad
PASS is forbidden until all three proofs exist:
1. workflow_dispatch_results status for Claude dispatcher.
2. claude_inbound_mailbox_workflow_state runtime start or completion.
3. real Claude response in governance/audit_mailbox/claude_to_gpt that is not NOT CLAUDE APPROVAL and not runtime blocker.

## Active blockers
- Real Claude response has not been proven.
- Protocol is not agreed until real Claude response is processed.
- Fallback/blocker files are not Claude approval.

## Operator decisions
1. Reports do not stop development.
2. Operator must not be used as relay for mailbox messages.
3. If Claude is contacted, monitoring must continue until result or a concrete blocker is repaired.
4. Broken queue JSON must be fixed directly; one bad JSON must not kill the runner.
5. New GPT and Claude chats need a canonical shared context file.

## Non-negotiable rules
- No issue comments.
- No secrets in files.
- Do not claim PASS without evidence.
- Do not count runtime blocker or NOT CLAUDE APPROVAL files as Claude response.
- If a checkpoint is sent to operator, a next active task or pending artifact must already exist.

## Next action
Continue repair loop from the latest governance/state BEM file. Prefer newest BEM state over stale handoff. If uncertain, verify proof triad and repair the first missing proof.
