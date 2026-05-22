#!/usr/bin/env bash
set -euo pipefail
bash scripts/git_safe_commit_push.sh "workflow dispatch queue results" || true
