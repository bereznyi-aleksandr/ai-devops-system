#!/usr/bin/env bash
# BEM-849: git safe push with pull-rebase retry
# Usage: bash scripts/git_push_with_retry.sh "commit message"
set -euo pipefail

MSG="${1:-Automated commit}"

git add -A 2>/dev/null || true
if git diff --cached --quiet; then
  echo "Nothing to commit"
  exit 0
fi

git commit -m "$MSG"

for attempt in 1 2 3; do
  if git pull --rebase --autostash origin main && git push origin HEAD:main; then
    echo "push_ok attempt=$attempt"
    git rev-parse HEAD
    exit 0
  fi
  echo "push_retry attempt=$attempt"
  sleep $((attempt * 2))
done

echo "push_failed after 3 attempts"
exit 1
