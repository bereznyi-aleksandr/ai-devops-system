#!/usr/bin/env bash
set -euo pipefail
msg="${1:-Automated repository update}"
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -A
if git diff --cached --quiet; then
  echo "No changes to commit"
  exit 0
fi
git commit -m "$msg"
for attempt in 1 2 3 4 5; do
  if git pull --rebase --autostash origin main && git push origin HEAD:main; then
    echo "safe_push_ok attempt=$attempt"
    exit 0
  fi
  echo "safe_push_retry attempt=$attempt"
  sleep $((attempt * 2))
done
echo "safe_push_failed"
exit 1
