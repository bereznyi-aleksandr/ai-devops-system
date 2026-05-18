# BEM-671 | Hourly Report YAML And Queue Cleanup

Дата: 2026-05-18 | 18:57 (UTC+3)

Fixes: delivery recorder is now a standalone script, `curator-hourly-report.yml` has no inline Python block, and workflow dispatch queue items are archived after handling so smoke messages do not repeat every task.
