# BEM-620 | Stale GitHub Run Failure Superseded

Дата: 2026-05-18 | 06:54 (UTC+3)

## Context
Operator screenshots show failed workflow runs from earlier commits before BEM-609 and BEM-614 fixes.

## Current rule
Do not treat old GitHub notification failures as current system state without checking latest workflow file and latest fix commits.

## Current action
Latest workflows were statically checked for no inline Python heredoc and conflict-safe commit steps. A new curator hourly report trigger was committed after the fixes.
