#!/usr/bin/env bash
set -euo pipefail
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -A governance/audit_mailbox/claude_to_gpt governance/state/claude_inbound_mailbox_workflow_state.json governance/state/claude_inbound_seen_items.json governance/reports/claude_inbound_mailbox_workflow_state.md governance/state governance/reports governance/transport governance/tmp/claude_inbound_preflight.env || true
git diff --cached --quiet && echo "No changes" || git commit -m "BEM-739 Claude inbound bridge state"
git pull --rebase --autostash origin main || true
git push || true
