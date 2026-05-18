# BEM-661 | Workflow Dispatch Queue

Дата: 2026-05-18 | 15:55 (UTC+3)

## Purpose
Commits created by GitHub Actions may not reliably trigger other workflows by push. `codex-runner.yml` now has `actions: write` and dispatches workflow queue items from `governance/workflow_dispatch_queue/*.json` via GitHub Actions API.

## Queue item
```json
{"workflow":"telegram-send-smoke.yml","ref":"main","inputs":{}}
```
