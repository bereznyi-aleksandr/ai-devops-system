# QUARANTINED WORKFLOW | claude-dispatch-bridge.yml

Дата: 2026-05-21 | 19:33 (UTC+3)
Причина: experimental Claude wake-up workflow caused repeated workflow-lint-gate failures. Kept as text artifact, not active GitHub workflow.

```yaml
name: Claude Dispatch Bridge

on:
  workflow_dispatch:
  push:
    paths:
      - 'governance/audit_mailbox/gpt_to_claude/**'
      - 'scripts/dispatch_claude_internal_auditor.sh'
      - '.github/workflows/claude-dispatch-bridge.yml'

permissions:
  contents: read
  actions: write

concurrency:
  group: claude-dispatch-bridge
  cancel-in-progress: false

jobs:
  dispatch-claude:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Dispatch Claude internal auditor workflow
        env:
          GH_TOKEN: ${{ secrets.AI_SYSTEM_GITHUB_PAT }}
        run: bash scripts/dispatch_claude_internal_auditor.sh

```
