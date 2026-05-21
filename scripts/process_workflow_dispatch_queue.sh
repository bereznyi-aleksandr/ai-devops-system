#!/usr/bin/env bash
set -euo pipefail
mkdir -p governance/workflow_dispatch_results
now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
count=0
for f in governance/workflow_dispatch_queue/*.json; do
  [ -f "$f" ] || continue
  count=$((count+1))
  base="$(basename "$f" .json)"
  out="governance/workflow_dispatch_results/${base}.status.json"
  workflow="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("workflow") or d.get("workflow_id") or d.get("file") or "")' "$f")"
  ref="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("ref") or "main")' "$f")"
  if [ -z "$workflow" ]; then
    printf '{"status":"missing_workflow","queue_file":"%s","time":"%s"}
' "$f" "$now" > "$out"
    continue
  fi
  if [ -z "${GH_TOKEN:-}" ]; then
    printf '{"status":"token_missing","queue_file":"%s","workflow":"%s","ref":"%s","time":"%s"}
' "$f" "$workflow" "$ref" "$now" > "$out"
    continue
  fi
  if gh workflow run "$workflow" --ref "$ref"; then
    printf '{"status":"dispatch_attempted","exit_code":0,"queue_file":"%s","workflow":"%s","ref":"%s","time":"%s"}
' "$f" "$workflow" "$ref" "$now" > "$out"
  else
    code=$?
    printf '{"status":"dispatch_failed","exit_code":%s,"queue_file":"%s","workflow":"%s","ref":"%s","time":"%s"}
' "$code" "$f" "$workflow" "$ref" "$now" > "$out"
  fi
done
echo "processed_queue_items=$count"
