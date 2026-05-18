# BEM-670 | Verify Operator Table Report Delivery | OPERATOR_TABLE_REPORT_NOT_FULLY_CONFIRMED

Дата: 2026-05-18 | 16:09 (UTC+3)

## Checks

- hourly_state_exists: PASS
- telegram_delivery_sent: PASS
- message_has_readable_table: FAIL
- message_has_no_raw_bem_events: PASS
- message_has_date_hour: FAIL
- workflow_runs_hourly: PASS

## Blocker
{
  "code": "OPERATOR_TABLE_REPORT_NOT_FULLY_CONFIRMED",
  "failed": [
    {
      "name": "message_has_readable_table",
      "pass": false,
      "evidence": "governance/reports/curator_hourly_report_runtime.md"
    },
    {
      "name": "message_has_date_hour",
      "pass": false,
      "evidence": "governance/reports/curator_hourly_report_runtime.md"
    }
  ],
  "delivery_text": "",
  "state": {
    "schema_version": "curator_hourly_report_state.v1",
    "status": "rendered",
    "message_file": "governance/tmp/curator_hourly_report_message.txt",
    "provider_checked": true,
    "selected_provider": "gpt_reserve",
    "reserve_used": true,
    "blocker": null,
    "event_count": 5,
    "created_at": "workflow_runtime",
    "telegram_delivery": "sent"
  }
}
