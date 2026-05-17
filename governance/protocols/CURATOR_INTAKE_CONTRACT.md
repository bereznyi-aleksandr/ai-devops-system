# BEM-531.01 | Curator Intake Contract

Дата: 2026-05-17 | 12:49 (UTC+3)

## Scope
Curator is the single entry point for BEM-531 internal role contour. Active sources: GPT, Claude and Telegram synthetic/webhook branch. Live Telegram API/token handling remains out of file scope and secrets must never be stored in repo files.

## Curator FSM
RECEIVED -> TRIAGED -> ASSIGNED -> WAITING_ROLE -> REVIEWING -> CLOSED

## Intake record schema
```json
{
  "record_type": "curator_intake",
  "cycle_id": "string",
  "source": "gpt|claude|telegram",
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
Telegram branch is active for synthetic/file-based curator intake in BEM-533. Live Telegram token/API integration is not required and secrets must not be written to files. Telegram records use `source=telegram` and `source_ref=telegram-webhook-synthetic` for tests.


## BEM-533 Telegram activation
Telegram synthetic/webhook branch is now included in curator intake schema. The branch enters through curator and then follows the same internal role cycle.
