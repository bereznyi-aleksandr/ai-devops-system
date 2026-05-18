# BEM-603 | Reply Intake Live Diagnostics

Дата: 2026-05-18 | 05:58 (UTC+3)

## Files
- workflow exists: True
- script exists: True
- trigger exists: True
- state exists: True
- result report exists: True

## Last run
{
  "http_status": "409",
  "webhook_http_status": "200",
  "webhook_active": true,
  "status": "blocked",
  "record": null,
  "blocker": {
    "code": "TELEGRAM_WEBHOOK_ACTIVE",
    "message": "Webhook is active; polling getUpdates may not receive replies reliably."
  }
}

## Decision files
[
  "governance/operator_decisions/bem584_decision_format_live_test.json"
]

## Status
blocked

## Blocker
{
  "code": "TELEGRAM_WEBHOOK_ACTIVE",
  "message": "Webhook is active; polling getUpdates may not receive replies reliably."
}
