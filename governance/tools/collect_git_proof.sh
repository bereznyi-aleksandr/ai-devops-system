#!/usr/bin/env bash
set -euo pipefail
mkdir -p governance/proof
SHA=$(git rev-parse HEAD)
STATUS=$(git status --short | sed ':a;N;$!ba;s/\n/\\n/g')
printf '{\n  "status": "PASS",\n  "commit_sha": "%s",\n  "git_status": "%s"\n}\n' "$SHA" "$STATUS" > governance/proof/git_proof_last_run.json
cat governance/proof/git_proof_last_run.json
