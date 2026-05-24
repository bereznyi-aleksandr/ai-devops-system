# BEM-840 | GPT-Claude Mailbox Mechanism Error Report

Дата: 2026-05-22 | 06:00 (UTC+3)

Status: system_ready

## PASS criteria
1. workflow_dispatch_results status exists: True
2. Claude runtime start/completion exists: True
3. real Claude response exists: True

## Current missing proofs
none

## Mechanism
GPT writes request to governance/audit_mailbox/gpt_to_claude or queues dispatch item in governance/workflow_dispatch_queue.
Codex Runner processes queue and should create governance/workflow_dispatch_results/*.status.json.
Claude dispatcher workflow should write governance/state/claude_inbound_mailbox_workflow_state.json.
Claude should write real response to governance/audit_mailbox/claude_to_gpt/.

## Main historical errors
- Malformed JSON in workflow_dispatch_queue caused JSONDecodeError and blocked queue processing.
- Fallback/blocker files were at risk of being confused with real Claude response; now they are explicitly filtered.
- Reports were incorrectly treated as stopping points; this is a process violation.

## Current conclusion
System is not proven ready until missing proofs are empty.
