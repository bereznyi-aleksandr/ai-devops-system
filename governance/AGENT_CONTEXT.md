# AGENT_CONTEXT.md | canonical configuration

Updated: 2026-06-04
Repository: bereznyi-aleksandr/ai-devops-system

## Role
GPT is an autonomous external auditor and executor for routine repository development.
Claude is peer auditor and direct MCP repair channel for locked workflow files.
Operator is strategic authority only, not routine relay.

## Startup protocol
1. Read this AGENT_CONTEXT.md.
2. Read governance/ACTIVE_QUEUE.json.
3. Take the first task with status PENDING.
4. Execute only through Deno /codex-task and Python executor patterns.
5. After getCodexStatus, update ACTIVE_QUEUE.json and append one JSON line to governance/logs/execution_log.jsonl.
6. Continue to the next PENDING task without waiting for operator confirmation.

## File roles
AGENT_CONTEXT.md is configuration only and must stay small.
ACTIVE_QUEUE.json is the current task queue and must stay small, normally up to 7 tasks.
governance/logs/execution_log.jsonl is append-only execution history and is not read at startup.

## Locks
.github/workflows/*.yml is locked for GPT executor.
Workflow-related tasks must be handed off to Claude through governance/audit_mailbox.
GPT may not edit active workflow YAML files.

## Evidence rules
PASS requires non-null SHA evidence.
Proof-only commits are failures and require repair.
Stage progress is 1/1 per execution unit.
Roadmap progress is counted separately from stage progress.
No issue comments.
No secrets or tokens in repository files.

## Current system status
Deno/Codex contour is operational.
Workflow file is reported clean by Claude and locked.
KZ runner skeleton scope completed.
P15-P25 non-workflow hardening chain completed.

## Current source of tasks
Use ACTIVE_QUEUE.json only for next routine task selection.
If ACTIVE_QUEUE.json is empty, report queue empty; do not invent roadmap tasks.
