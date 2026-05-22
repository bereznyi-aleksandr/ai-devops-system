#!/usr/bin/env bash
set -euo pipefail
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -A governance/state/queue_processor_step_seen.json governance/workflow_dispatch_results/queue_processor_step_seen.status.json governance/workflow_dispatch_results || true
git diff --cached --quiet && echo "No queue marker/result changes" || git commit -m "BEM-843 queue processor marker/results"
git pull --rebase --autostash origin main || true
git push || true
