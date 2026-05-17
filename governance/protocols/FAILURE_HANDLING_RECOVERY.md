# BEM-550.8 | Failure Handling and Recovery

Дата: 2026-05-17 | 15:40 (UTC+3)

## Unified blocker format
`code`, `message`, `source`, `next_action`, `created_at`.

## Policy
failed/cancelled/timeout -> curator receives blocker -> retry once only if safe -> otherwise final report with exact blocker. No issue #31.
