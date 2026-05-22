#!/usr/bin/env bash
set -euo pipefail
mkdir -p governance/state governance/workflow_dispatch_results
now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '{"status":"queue_processor_step_seen","time":"%s"}\n' "$now" > governance/state/queue_processor_step_seen.json
printf '{"status":"queue_processor_step_seen","time":"%s"}\n' "$now" > governance/workflow_dispatch_results/queue_processor_step_seen.status.json
