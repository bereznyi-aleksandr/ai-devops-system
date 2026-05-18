# BEM-673 | Verify Canonical Hourly Dispatch And Delivery | CANONICAL_HOURLY_NOT_CONFIRMED

Дата: 2026-05-18 | 18:59 (UTC+3)

## Checks

- dispatch_status_204: PASS
- queue_archived: FAIL
- active_queue_empty: PASS
- hourly_state_exists: PASS
- telegram_delivery_sent: PASS
- operator_table_present: PASS
- raw_events_removed: PASS

## Blocker
{
  "code": "CANONICAL_HOURLY_NOT_CONFIRMED",
  "failed": [
    {
      "name": "queue_archived",
      "pass": false,
      "evidence": "governance/workflow_dispatch_processed/"
    }
  ],
  "status_file": "204\n",
  "response_preview": null,
  "hourly_state": {
    "schema_version": "curator_hourly_report_state.v2",
    "status": "sent",
    "report_hour": "2026-05-18 | 19:00 (UTC+3)",
    "stage_done": 6,
    "stage_total": 6,
    "stage_percent": 100,
    "roadmap_done": 6,
    "roadmap_total": 6,
    "roadmap_percent": 100,
    "telegram_delivery": "sent",
    "rows": [
      {
        "number": 1,
        "name": "Write-channel",
        "essence": "runner restored",
        "status": "✅"
      },
      {
        "number": 2,
        "name": "Role-bus",
        "essence": "roles and lanes checked",
        "status": "✅"
      },
      {
        "number": 3,
        "name": "Provider route",
        "essence": "primary/reserve explicit",
        "status": "✅"
      },
      {
        "number": 4,
        "name": "Telegram smoke",
        "essence": "direct send proof",
        "status": "✅"
      },
      {
        "number": 5,
        "name": "Hourly report",
        "essence": "hourly delivery",
        "status": "✅"
      },
      {
        "number": 6,
        "name": "Readiness",
        "essence": "final acceptance",
        "status": "✅"
      }
    ],
    "blocker": null
  },
  "delivery_report": "# Curator Hourly Delivery\n\nTelegram delivery: sent\n"
}
