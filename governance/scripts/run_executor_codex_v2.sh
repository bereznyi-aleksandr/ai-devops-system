#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT_DIR"

PROMPT_FILE="governance/prompts/executor_codex_system_prompt_v3_7.txt"
PACKET_FILE="governance/runtime/packets/executor_packet_current.json"
RESULT_FILE="governance/runtime/results/executor_materialize_result.json"
FAILURE_WRITER="governance/scripts/system_failure_result_writer_v1.py"

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
TASK_ID="$(python3 - <<'PY'
import json
from pathlib import Path
p = Path('governance/runtime/packets/executor_packet_current.json')
data = json.loads(p.read_text(encoding='utf-8'))
print(str(data.get('task_id', '')).strip())
PY
)"

write_failure() {
  local details="$1"
  python3 "$FAILURE_WRITER" EXECUTOR "$TASK_ID" "$details" || true
}

cat > /tmp/executor_codex_input.txt <<'EOF'
You are running inside GitHub Codespaces as EXECUTOR.

Read the system prompt and packet below.
Then perform exactly one allowed EXECUTOR action.
Write the required canonical artifact.
Then write governance/runtime/results/executor_materialize_result.json.

Do not modify exchange_ledger.csv.
Do not merge.
Do not invent state.

===== SYSTEM PROMPT =====
EOF

printf '%s\n' "$PROMPT_CONTENT" >> /tmp/executor_codex_input.txt
printf '\n===== CURRENT PACKET =====\n' >> /tmp/executor_codex_input.txt
printf '%s\n' "$PACKET_CONTENT" >> /tmp/executor_codex_input.txt

CODEX_PROMPT="$(cat /tmp/executor_codex_input.txt)"
if ! codex --full-auto "$CODEX_PROMPT"; then
  write_failure "Codex executor run failed"
  exit 1
fi

if [[ ! -f "$RESULT_FILE" ]]; then
  write_failure "Missing $RESULT_FILE after Codex run"
  echo "Missing $RESULT_FILE after Codex run" >&2
  exit 1
fi

python3 - <<'PY'
import json, pathlib, sys
p = pathlib.Path('governance/runtime/results/executor_materialize_result.json')
data = json.loads(p.read_text(encoding='utf-8'))
required = {
    'role','protocol_version','task_id','parent_event_id','input_event_id',
    'next_action_processed','result','produced_artifact_type','produced_artifact_path',
    'proof_ref','summary','risk_notes','rollback_notes','blocked_reason','touched_files','ts_utc'
}
missing = [k for k in required if k not in data]
if missing:
    print('Missing required fields: ' + ', '.join(missing), file=sys.stderr)
    sys.exit(1)
if data['role'] != 'EXECUTOR':
    print('Invalid role in result manifest', file=sys.stderr)
    sys.exit(1)
print('executor_materialize_result.json validated')
PY

echo "EXECUTOR run complete"
