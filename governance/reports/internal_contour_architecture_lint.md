# Internal Contour Architecture Lint

Status: pass

## Checks
- role_communication_canon_exists: PASS | governance/protocols/ROLE_COMMUNICATION_CANON.md
- role_execution_evidence_canon_exists: PASS | governance/protocols/ROLE_EXECUTION_EVIDENCE_CANON.md
- bem605_internal_auditor_package_exists: PASS | governance/internal_contour/auditor/inbox/bem625_bem605_hourly_report_internal_auditor_review.json
- bem605_mailbox_misroute_annotated: PASS | governance/audit_mailbox/meta/bem625_bem605_mailbox_misroute_annotation.json
- auditor_to_auditor_mailbox_lane_exists: PASS | governance/audit_mailbox/internal_auditor_to_external_auditor
- provider_route_has_provider_checked: PASS | governance/provider_gates/bem610_provider_route_decision.json
- provider_route_has_primary_provider: PASS | governance/provider_gates/bem610_provider_route_decision.json
- provider_route_has_reserve_provider: PASS | governance/provider_gates/bem610_provider_route_decision.json
- provider_route_has_selected_provider: PASS | governance/provider_gates/bem610_provider_route_decision.json
- provider_route_has_reserve_used: PASS | governance/provider_gates/bem610_provider_route_decision.json
- provider_route_has_reason: PASS | governance/provider_gates/bem610_provider_route_decision.json
- historical_bem605_mailbox_misroute_not_unannotated: PASS | governance/audit_mailbox/gpt_to_claude/bem605_hourly_report_template_review_request.md
- deno_labeled_transport_not_executor: PASS | governance/protocols/ROLE_COMMUNICATION_CANON.md

## Blocker
null
