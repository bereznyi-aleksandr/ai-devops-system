# BEM-619 | Full Monitoring Report | Hourly Report Pipeline

Дата: 2026-05-18 | 06:51 (UTC+3)

## Summary
Status: completed_with_live_delivery_live_sent
Selected provider: gpt_reserve
Reserve used: True
Live Telegram delivery: sent

## Elements
- Curator: PASS | Operator task accepted into curator inbox. | evidence: governance/curator/inbox/bem605_hourly_report_canon_template.json
- Registrar/Role Orchestrator: PASS | Curator package routed to role orchestrator. | evidence: governance/role_orchestrator/inbox/bem605_hourly_report_canon_template.json
- Analyst GPT: PASS | Analyst prepared template and questions. | evidence: governance/internal_contour/analyst/plans/bem605_hourly_report_template_plan.json
- Claude auditor mailbox: PASS | Claude review item written to mailbox. | evidence: governance/audit_mailbox/gpt_to_claude/bem605_hourly_report_template_review_request.md
- Provider gate: PASS | Provider route recorded: selected=gpt_reserve reserve_used=True | evidence: governance/provider_gates/bem610_provider_route_decision.json
- Reserve audit: PASS | GPT reserve audit used because Claude runtime was not proven/available in time. | evidence: governance/internal_contour/auditor/reports/bem612_reserve_audit_hourly_report_template.json
- Executor item: PASS | Execution item created for renderer implementation. | evidence: governance/internal_contour/executor/inbox/bem612_execute_hourly_report_canon.json
- Renderer: PASS | Canonical hourly report renderer implemented. | evidence: scripts/render_curator_hourly_report.py
- Workflow: PASS | Allowed schedule workflow updated. | evidence: .github/workflows/curator-hourly-report.yml
- Selftest: FAIL | Static selftest status=failed | evidence: governance/state/bem617_hourly_report_static_selftest_safe.json
- Live Telegram delivery: PASS | Delivery status=sent | evidence: governance/state/curator_hourly_report_state.json

## Blocker
{
  "code": "HOURLY_PIPELINE_MONITORING_FINDINGS",
  "failed": [
    {
      "element": "Selftest",
      "status": "FAIL",
      "evidence": "governance/state/bem617_hourly_report_static_selftest_safe.json",
      "comment": "Static selftest status=failed"
    }
  ]
}
