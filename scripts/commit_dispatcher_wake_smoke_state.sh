#!/usr/bin/env bash
set -euo pipefail
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -A governance/state/dispatcher_wake_smoke_state.json governance/reports/dispatcher_wake_smoke_state.md || true
git diff --cached --quiet && echo "No changes" || git commit -m "BEM-767 dispatcher wake smoke state"
git pull --rebase --autostash origin main || true
git push || true
