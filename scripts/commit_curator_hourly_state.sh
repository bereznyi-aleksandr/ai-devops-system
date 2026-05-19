#!/usr/bin/env bash
set -euo pipefail
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
paths=(
  "governance/state/curator_hourly_report_state.json"
  "governance/state/curator_hourly_report_last_snapshot.json"
  "governance/reports/curator_hourly_report_runtime.md"
  "governance/tmp/curator_hourly_report_delivery.txt"
  "governance/tmp/curator_hourly_report_response.json"
)
for path in "${paths[@]}"; do
  if [[ -e "$path" ]]; then
    git add "$path"
  fi
done
if git diff --cached --quiet; then
  echo "No changes"
else
  git commit -m "BEM-HOURLY curator report state"
fi
git pull --rebase --autostash origin main || true
git push || true
