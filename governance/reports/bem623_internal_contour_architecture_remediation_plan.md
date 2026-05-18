# BEM-623 | Internal Contour Architecture Remediation Plan

Дата: 2026-05-18 | 07:03 (UTC+3)

## Goal
Close architecture gaps found during BEM-622 internal contour deep audit.

## Items
### R1 | Claude primary runtime not proven
- Fix: Add mandatory Claude-authored smoke response artifact before selecting Claude primary. If absent, selected_provider must be gpt_reserve with blocker/reason.
- Evidence required: governance/audit_mailbox/claude_to_gpt/*response*.md, governance/provider_gates/*claude_runtime_smoke*.json

### R2 | Live Telegram delivery not confirmed
- Fix: Add post-trigger delivery verifier that checks curator_hourly_report_state.telegram_delivery=sent and creates alert/report if not sent.
- Evidence required: governance/state/curator_hourly_report_state.json, governance/reports/curator_hourly_report_runtime.md

### R3 | Old failed workflow notifications confuse operator
- Fix: Add current-run supersede report and suppress false PASS. Keep stale failures tagged as superseded only after latest workflow static validation.
- Evidence required: governance/state/bem620_supersede_old_failed_runs_and_live_trigger.json

### R4 | Executor sandbox restrictions caused repeated selftest failures
- Fix: Document executor-safe subset and add preflight linter for task objectives: no exec call, no Exception as e, no forbidden module words.
- Evidence required: governance/protocols/PYTHON_EXECUTOR_SAFE_SUBSET.md, scripts/executor_objective_preflight.py

### R5 | File-based roles can look like live LLM roles
- Fix: Report must explicitly distinguish live provider role vs file-based governance artifact role.
- Evidence required: governance/protocols/ROLE_EXECUTION_EVIDENCE_CANON.md

## Next execution order
- R4
- R1
- R2
- R5
- R3

## Blocker
null
