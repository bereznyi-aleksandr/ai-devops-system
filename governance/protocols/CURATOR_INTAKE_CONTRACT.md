# BEM-531.01 | Curator Intake Contract

Дата: 2026-05-17 | 12:49 (UTC+3)

## Scope
Curator is the single entry point for BEM-531 internal role contour. Active sources in BEM-531: GPT and Claude. Telegram is reserved/deferred.

## Curator FSM
RECEIVED -> TRIAGED -> ASSIGNED -> WAITING_ROLE -> REVIEWING -> CLOSED

## Intake record schema
```json
{
  "record_type": "curator_intake",
  "cycle_id": "string",
  "source": "gpt|claude|telegram_deferred",
  "source_ref": "string",
  "request_title": "string",
  "request_body": "string",
  "priority": "low|normal|high",
  "curator_status": "RECEIVED|TRIAGED|ASSIGNED|WAITING_ROLE|REVIEWING|CLOSED",
  "next_role": "analyst|auditor|executor|curator",
  "blocker": null,
  "created_at": "UTC+3 timestamp"
}
```

## Assignment rules
- New ambiguous task -> analyst.
- Patch-ready task -> auditor before executor.
- Approved patch -> executor.
- Executor result -> auditor final check.
- Final PASS/BLOCKER -> curator closure.

## Telegram policy
Telegram branch is part of the broader architecture but deferred out of BEM-531 execution scope. Records may reserve `source=telegram_deferred`, but no Telegram E2E is required in BEM-531.
