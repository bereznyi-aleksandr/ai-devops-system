#!/usr/bin/env bash
set -euo pipefail
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -A governance/state/claude_inbound_mailbox_workflow_state.json governance/audit_mailbox/claude_to_gpt governance/reports || true
git diff --cached --quiet && echo "No Claude dispatcher changes" || git commit -m "BEM-833B Claude dispatcher state mailbox"
git pull --rebase --autostash origin main || true
git push || true
