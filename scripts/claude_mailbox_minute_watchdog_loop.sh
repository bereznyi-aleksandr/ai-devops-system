#!/usr/bin/env bash
set -euo pipefail
for i in $(seq 1 120); do
  python3 scripts/claude_mailbox_minute_watchdog.py
  STATUS=$(python3 scripts/read_claude_watchdog_status.py)
  git config user.name "github-actions[bot]"
  git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  git add -A governance/state/claude_mailbox_minute_watchdog_state.json governance/reports/claude_mailbox_minute_watchdog_report.md governance/handoff/GPT_NEXT_ACTION.md governance/tasks/pending/claude_mailbox_autoprocess_next.md governance/agreements/final
  git diff --cached --quiet && echo "No changes" || git commit -m "BEM-722B claude mailbox minute watchdog tick"
  git pull --rebase --autostash origin main || true
  git push || true
  case "$STATUS" in result_approved|result_change_required|result_blocked) exit 0 ;; esac
  sleep 60
done
