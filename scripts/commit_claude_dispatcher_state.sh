#!/usr/bin/env bash
set -euo pipefail
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -A governance/audit_mailbox/claude_to_gpt governance/state/claude_inbound_mailbox_workflow_state.json governance/reports/claude_inbound_mailbox_workflow_state.md governance/tmp/claude_active.env || true
git diff --cached --quiet && echo "No changes" || git commit -m "BEM-753 Claude dispatcher state"
git pull --rebase --autostash origin main || true
git push || true
