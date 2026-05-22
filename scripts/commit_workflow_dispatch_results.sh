#!/usr/bin/env bash
set -euo pipefail
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -A governance/workflow_dispatch_results governance/state/workflow_dispatch_queue_processor_marker.json governance/workflow_dispatch_queue governance/workflow_dispatch_queue_invalid || true
git diff --cached --quiet && echo "No dispatch result changes" || git commit -m "BEM-783 workflow dispatch queue results"
git pull --rebase --autostash origin main || true
git push || true
