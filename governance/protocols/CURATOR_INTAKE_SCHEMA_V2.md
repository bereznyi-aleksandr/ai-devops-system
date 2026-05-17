# BEM-548.1 | Curator Intake Schema v2

Дата: 2026-05-17 | 14:52 (UTC+3)

## Required fields
| Field | Type | Rule |
|---|---|---|
| trace_id | string | unique, non-empty |
| source | enum | gpt, claude, telegram |
| task_type | enum | development, audit, hotfix |
| title | string | non-empty |
| objective | string | non-empty |
| created_at | string | UTC+3 timestamp preferred |
| blocker | null/object | null for accepted tasks |

## Duplicate rule
If trace_id already exists in transport, curator must reject duplicate with blocker code `DUPLICATE_TRACE_ID`.

## Invalid schema rule
Missing/invalid fields produce blocker code `CURATOR_INTAKE_SCHEMA_INVALID`.

## Source audit
Every accepted/rejected intake writes `curator_intake_validation` to `governance/transport/results.jsonl`.
