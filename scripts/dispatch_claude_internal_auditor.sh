#!/usr/bin/env bash
set -euo pipefail
if [ -z "${GH_TOKEN:-}" ]; then
  echo "GH_TOKEN missing"
  exit 1
fi
gh workflow run claude-internal-auditor-dispatcher.yml --ref main
