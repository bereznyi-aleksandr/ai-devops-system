# QUARANTINED WORKFLOW | claude-internal-auditor-dispatcher.yml

Дата: 2026-05-21 | 19:33 (UTC+3)
Причина: experimental Claude wake-up workflow caused repeated workflow-lint-gate failures. Kept as text artifact, not active GitHub workflow.

```yaml
name: Claude Internal Auditor Dispatcher

on:
  workflow_dispatch:
  workflow_run:
    workflows: ["Codex Runner"]
    types:
      - completed

permissions:
  contents: write
  issues: write

concurrency:
  group: claude-internal-auditor-dispatcher
  cancel-in-progress: false

jobs:
  claude-internal-auditor:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Syntax check helper scripts
        run: python3 -m py_compile scripts/check_claude_mailbox_work.py scripts/record_claude_inbound_workflow_state.py
      - name: Check active mailbox work
        id: active_check
        run: |
          python3 scripts/check_claude_mailbox_work.py > governance/tmp/claude_active.env
          cat governance/tmp/claude_active.env >> "$GITHUB_OUTPUT"
      - name: Record dispatcher start
        if: steps.active_check.outputs.active == 'true'
        run: python3 scripts/record_claude_inbound_workflow_state.py start dispatcher_started
      - name: Claude internal auditor responds to mailbox
        if: steps.active_check.outputs.active == 'true'
        id: claude_response
        continue-on-error: true
        uses: anthropics/claude-code-action@v1
        env:
          CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          prompt: |
            You are Claude Internal Auditor for repository bereznyi-aleksandr/ai-devops-system.
            Read the newest file in governance/audit_mailbox/gpt_to_claude/.
            Write response to governance/audit_mailbox/claude_to_gpt/ with BEM id in filename.
            Include Decision: APPROVED / CHANGE_REQUIRED / BLOCKED when asked.
            Explain why prior mailbox response was missing when asked.
            Do not write issue comments. Do not expose secrets.
          claude_args: |
            --max-turns 8
      - name: Record dispatcher completion
        if: steps.active_check.outputs.active == 'true' && always()
        env:
          CLAUDE_OUTCOME: ${{ steps.claude_response.outcome }}
        run: python3 scripts/record_claude_inbound_workflow_state.py complete "$CLAUDE_OUTCOME"
      - name: Commit dispatcher state
        if: always()
        run: bash scripts/commit_claude_dispatcher_state.sh

```
