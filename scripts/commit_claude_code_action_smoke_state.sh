#!/usr/bin/env bash
set -euo pipefail
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -A governance/state/claude_code_action_smoke_state.json governance/reports/claude_code_action_smoke_state.md governance/audit_mailbox/claude_to_gpt || true
git diff --cached --quiet && echo "No smoke state changes" || git commit -m "BEM-863C Claude Code Action smoke state"
git pull --rebase --autostash origin main || true
git push || true
