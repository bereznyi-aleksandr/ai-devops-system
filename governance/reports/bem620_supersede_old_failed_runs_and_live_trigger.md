# BEM-620 | Supersede Old Failed Runs And Live Trigger | WARN

Дата: 2026-05-18 | 06:54 (UTC+3)

## Result
static_validation_failed_live_trigger_committed

## Checks

- curator_hourly_exists: PASS
- curator_hourly_no_inline_python_heredoc: PASS
- curator_hourly_conflict_safe_commit: PASS
- provider_gate_exists: PASS
- provider_gate_no_inline_python_heredoc: PASS
- provider_gate_conflict_safe_commit: PASS
- role_router_exists: PASS
- role_router_no_inline_python_heredoc: PASS
- role_router_conflict_safe_commit: PASS
- mailbox_dispatcher_exists: PASS
- mailbox_dispatcher_no_inline_python_heredoc: PASS
- mailbox_dispatcher_conflict_safe_commit: PASS
- schedule_only_curator_hourly: FAIL

## Live trigger
governance/triggers/curator_hourly_report.trigger

## Blocker
{
  "code": "WORKFLOW_STATIC_VALIDATION_FAILED",
  "failed": [
    {
      "name": "schedule_only_curator_hourly",
      "pass": false,
      "schedule_files": [
        ".github/workflows/curator-hourly-report.yml",
        ".github/workflows/telegram-outbox-dispatch.yml"
      ]
    }
  ]
}
