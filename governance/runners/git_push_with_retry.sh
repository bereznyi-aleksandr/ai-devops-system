#!/usr/bin/env bash
set -euo pipefail

BRANCH="${1:-main}"
REMOTE="${2:-origin}"
MAX_ATTEMPTS="${MAX_PUSH_ATTEMPTS:-3}"

echo "BEM-946 safe push: remote=${REMOTE} branch=${BRANCH} attempts=${MAX_ATTEMPTS}"

for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  echo "BEM-946 safe push attempt ${attempt}/${MAX_ATTEMPTS}"
  git fetch "$REMOTE" "$BRANCH"
  if git rev-parse --verify "${REMOTE}/${BRANCH}" >/dev/null 2>&1; then
    git rebase "${REMOTE}/${BRANCH}" || {
      echo "Rebase failed; aborting rebase and failing safely"
      git rebase --abort || true
      exit 1
    }
  fi
  if git push "$REMOTE" "HEAD:${BRANCH}"; then
    echo "BEM-946 safe push PASS"
    git rev-parse HEAD > governance/codex/last_pushed_sha.txt || true
    exit 0
  fi
  echo "Push rejected; retrying after remote sync"
  sleep $((attempt * 2))
done

echo "BEM-946 safe push FAIL after ${MAX_ATTEMPTS} attempts"
exit 1
