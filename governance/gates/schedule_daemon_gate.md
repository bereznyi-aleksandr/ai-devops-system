# Schedule / daemon gate

Status: OPERATOR_GATE

Rule:
- New schedule triggers are forbidden unless approved by operator.
- Always-on daemon mode is forbidden unless approved by operator.
- Existing allowed baseline remains workflow_dispatch.
- curator-hourly-report.yml exception remains governed by operator report period config.

No issue comments.
