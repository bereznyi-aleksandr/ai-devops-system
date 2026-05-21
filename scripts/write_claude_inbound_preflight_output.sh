#!/usr/bin/env bash
set -euo pipefail
python3 scripts/prepare_claude_inbound_context.py > governance/tmp/claude_inbound_preflight.env
cat governance/tmp/claude_inbound_preflight.env >> "$GITHUB_OUTPUT"
