# BEM-531.2 | File Transport Contract + Failure Handling

Дата: 2026-05-17 | 12:50 (UTC+3)

## Purpose
Defines JSONL records for internal role contour exchange. Active file: `governance/transport/results.jsonl`.

## Record types
- intake
- handoff
- analysis
- audit
- execution
- final_result
- role_timeout
- role_failed
- validation_failed
- executor_failed

## Common fields
```json
{
  "record_type": "string",
  "cycle_id": "string",
  "source": "gpt|claude|telegram_deferred|internal",
  "from_role": "curator|analyst|auditor|executor",
  "to_role": "curator|analyst|auditor|executor",
  "status": "queued|in_progress|completed|failed|blocked",
  "artifact_path": "string",
  "commit_sha": "string|null",
  "blocker": "object|null",
  "created_at": "UTC+3 timestamp"
}
```

## Failure records
- role_timeout: role did not produce artifact inside expected window.
- role_failed: role produced blocker.
- validation_failed: schema or artifact validation failed.
- executor_failed: GitHub Actions/Python executor failed.

## Recovery fields
Failure records must include `retry_allowed`, `next_action`, `escalation_target`, `failure_reason`.

## Rules
- No issue #31 comments.
- No schedule triggers.
- No secrets in files.
- No paid OpenAI API.
