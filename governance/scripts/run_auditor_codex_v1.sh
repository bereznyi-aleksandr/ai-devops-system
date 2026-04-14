#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT_DIR"

PROMPT_FILE="governance/prompts/auditor_codex_system_prompt_v3_7.txt"
PACKET_FILE="governance/runtime/packets/auditor_packet_current.json"
RESULT_FILE="governance/runtime/results/auditor_materialize_result.json"

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "Missing $PROMPT_FILE" >&2
  exit 1
fi

if [[ ! -f "$PACKET_FILE" ]]; then
  echo "Missing $PACKET_FILE" >&2
  exit 1
fi

mkdir -p governance/runtime/results

PACKET_CONTENT="$(cat "$PACKET_FILE")"
PROMPT_CONTENT="$(cat "$PROMPT_FILE")"

cat > /tmp/auditor_codex_input.txt <<'EOF'
You are running inside GitHub Codespaces as AUDITOR.

Read the system prompt and packet below.
Then perform exactly one allowed AUDITOR action.
Write the required canonical decision artifact.
Then write governance/runtime/results/auditor_materialize_result.json.

Do not modify governance/exchange_ledger.csv.
Do not merge.
Do not implement product changes.

===== SYSTEM PROMPT =====
EOF

printf '%s\n' "$PROMPT_CONTENT" >> /tmp/auditor_codex_input.txt
printf '\n===== CURRENT PACKET =====\n' >> /tmp/auditor_codex_input.txt
printf '%s\n' "$PACKET_CONTENT" >> /tmp/auditor_codex_input.txt

CODEX_PROMPT="$(cat /tmp/auditor_codex_input.txt)"
codex --full-auto "$CODEX_PROMPT"

if [[ ! -f "$RESULT_FILE" ]]; then
  echo "Missing $RESULT_FILE after Codex run" >&2
  exit 1
fi

python3 - <<'PY'
import json, pathlib, sys
p = pathlib.Path('governance/runtime/results/auditor_materialize_result.json')
data = json.loads(p.read_text(encoding='utf-8'))
required = [
    'role','protocol_version','task_id','parent_event_id','input_event_id',
    'next_action_processed','result','produced_artifact_type','produced_artifact_path',
    'reviewed_ref','reviewed_commit_sha','summary','rationale','conditions','blocked_reason','touched_files','ts_utc'
]
missing = [k for k in required if k not in data]
if missing:
    print('Missing required fields: ' + ', '.join(missing), file=sys.stderr)
    sys.exit(1)
if data['role'] != 'AUDITOR':
    print('Invalid role in result manifest', file=sys.stderr)
    sys.exit(1)
print('auditor_materialize_result.json validated')
PY

echo "AUDITOR run complete"
