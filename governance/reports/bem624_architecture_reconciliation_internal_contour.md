# BEM-624 | Architecture Reconciliation | Internal Contour

Дата: 2026-05-18 | 07:05 (UTC+3)

## Verdict
Current BEM-605..621 run used internal file artifacts, but violated the intended communication separation: audit_mailbox was used where internal role-bus should be primary. Claude primary runtime was not proven, so reserve path was correct but must be represented clearly.

## Actual artifacts
- curator_inbox: exists | governance/curator/inbox/bem605_hourly_report_canon_template.json
- role_orchestrator: exists | governance/role_orchestrator/inbox/bem605_hourly_report_canon_template.json
- internal_task: exists | governance/internal_contour/tasks/bem605_hourly_report_canon_template.json
- analyst_plan: exists | governance/internal_contour/analyst/plans/bem605_hourly_report_template_plan.json
- internal_auditor_inbox: exists | governance/internal_contour/auditor/inbox/bem605_hourly_report_template_claude_audit.json
- wrong_mailbox_to_claude: exists | governance/audit_mailbox/gpt_to_claude/bem605_hourly_report_template_review_request.md
- provider_route: exists | governance/provider_gates/bem610_provider_route_decision.json
- reserve_audit: exists | governance/internal_contour/auditor/reports/bem612_reserve_audit_hourly_report_template.json
- executor_item: exists | governance/internal_contour/executor/inbox/bem612_execute_hourly_report_canon.json

## Gaps
### G1 | Mailbox used as internal role communication
- Expected: Internal roles communicate through role_orchestrator/internal_contour inboxes; audit_mailbox is only for external<->internal auditor sync.
- Actual: BEM-605 sent analyst->Claude auditor request through governance/audit_mailbox/gpt_to_claude.
- Severity: high
- Fix: Create internal role-bus canon, move/duplicate BEM-605 audit request into internal_contour/auditor/inbox, mark mailbox copy as external-audit-copy only, and add validator.

### G2 | External auditor link missing in chain
- Expected: External auditor and internal auditor coordinate through audit_mailbox; operator is not relay.
- Actual: Only GPT->Claude mailbox was created; no explicit internal_auditor<->external_auditor decision thread was modeled.
- Severity: high
- Fix: Create external_internal_audit_sync package and route only auditor-to-auditor messages via audit_mailbox.

### G3 | Claude primary provider proof incomplete
- Expected: Before fallback, system checks Claude runtime/limits and records proof.
- Actual: Provider gate recorded primary not proven and selected GPT reserve; no Claude-authored runtime artifact.
- Severity: high
- Fix: Add Claude runtime proof contract: primary cannot be selected without Claude-authored artifact; otherwise automatic reserve with reason.

### G4 | Deno role confusion
- Expected: Deno is external GPT write transport, not internal executor role. Internal executor should be Codex/direct repo write when available.
- Actual: All repo writes from this ChatGPT session used Deno /codex-task because that is the available write channel here.
- Severity: medium
- Fix: Document Deno as external transport adapter only; introduce execution_adapter field distinguishing deno_transport from internal executor.

### G5 | Live Telegram delivery not proven
- Expected: Hourly report delivery state should say sent.
- Actual: BEM-621 did not confirm sent.
- Severity: medium
- Fix: Keep delivery blocker until live state confirms sent and add delivery verifier.

## Scanned files
- governance/AGENT_ROLES.md
- governance/AUDIT_DIFF_PROTOCOL.md
- governance/EXTERNAL_AUDITOR_CONTRACT.md
- governance/GPT_ARCHITECTURE_UPDATE.md
- governance/GPT_HANDOFF.md
- governance/GPT_WRITE_CHANNEL.md
- governance/INTERNAL_CONTOUR_REFERENCE.md
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/reports/bem531_full_curator_entry_architecture_audit.md
- governance/archive/bem531_00_cleanup_preflight_20260517/governance/tasks/pending/BEM530_INTERNAL_CONTOUR_IMPROVEMENT_ROADMAP.md
- governance/archive/bem532_20260517_phase1/governance/tasks/pending/P8_FULL_ROLE_CYCLE_E2E.md
- governance/archive/legacy-2026-05-01/full-repo-cleanup/governance/consolidated_architecture_v3_v4_v5.md
- governance/archive/legacy-2026-05-01/full-repo-cleanup/governance/fixtures/gha_e2e/AUDIT-TASK-GHA-E2E-001-AUTO-0001.json
- governance/codex/proofs/bem535_1_architecture_contract.txt
- governance/codex/proofs/bem623_internal_contour_architecture_remediation_plan.txt
- governance/codex/results/bem535_1_architecture_contract.json
- governance/codex/results/bem535_1_architecture_contract.md
- governance/codex/results/bem623_internal_contour_architecture_remediation_plan.json
- governance/codex/results/bem623_internal_contour_architecture_remediation_plan.md
- governance/codex/tasks/bem535_1_architecture_contract.json
- governance/codex/tasks/bem623_internal_contour_architecture_remediation_plan.json
- governance/codex/tasks/bem624_architecture_reconciliation_internal_contour.json
- governance/protocols/ACTIVE_ANALYST_ROLE_OPERATOR_DECISION.md
- governance/protocols/ACTIVE_CURATOR_ROLE_OPERATOR_DECISION.md
- governance/protocols/EXTERNAL_AUDIT_TO_INTERNAL_CURATOR_HANDOFF.md
- governance/protocols/HANDOFF_PROTOCOL_CLAUDE_GPT.md
- governance/protocols/INTERNAL_CONTOUR_ARCHITECTURE_GAP_CLOSURE.md
- governance/protocols/MAILBOX_TELEGRAM_DECISION_ONLY_POLICY.md
- governance/protocols/MAILBOX_TELEGRAM_OPERATOR_FYI_FORMAT.md
- governance/protocols/OPERATOR_DECISION_CURATOR_HANDOFF.md
- governance/protocols/PEER_AUDITORS_DECISION_TO_CURATOR.md
- governance/protocols/PROVIDER_GATE_CLAUDE_AUDIT_POLICY.md
- governance/protocols/ROLE_ORCHESTRATOR_INTERNAL_ROUTER.md
- governance/protocols/ROLE_ORCHESTRATOR_WORKFLOW_PARITY.md
- governance/protocols/ROLE_STATE_SCHEMA.md
- governance/reports/bem535_1_provider_architecture_contract.md
- governance/reports/bem623_internal_contour_architecture_remediation_plan.md
- governance/state/bem623_internal_contour_architecture_remediation_plan.json
- governance/tasks/done/BEM531_INTERNAL_ROLE_CONTOUR_ROADMAP.md
- governance/tasks/done/BEM536_INTERNAL_CONTOUR_AUTOTEST_ROADMAP.md
- governance/tasks/done/P8_FULL_ROLE_CYCLE_E2E.md
- governance/tasks/done/P9_HANDOFF_PROTOCOL.md
