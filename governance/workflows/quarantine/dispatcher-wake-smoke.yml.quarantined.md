# QUARANTINED WORKFLOW | dispatcher-wake-smoke.yml

Дата: 2026-05-21 | 19:33 (UTC+3)
Причина: experimental Claude wake-up workflow caused repeated workflow-lint-gate failures. Kept as text artifact, not active GitHub workflow.

```yaml
name: Dispatcher Wake Smoke

on:
  workflow_dispatch:
  workflow_run:
    workflows: ["Codex Runner "]
    types:
      - completed

permissions:
  contents: write

concurrency:
  group: dispatcher-wake-smoke
  cancel-in-progress: false

jobs:
  smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Syntax check
        run: python3 -m py_compile scripts/record_dispatcher_wake_smoke.py
      - name: Record wake smoke
        run: python3 scripts/record_dispatcher_wake_smoke.py
      - name: Commit wake smoke state
        run: bash scripts/commit_dispatcher_wake_smoke_state.sh

```
