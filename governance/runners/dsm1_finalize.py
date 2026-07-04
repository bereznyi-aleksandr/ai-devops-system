#!/usr/bin/env python3
"""DSM-1 identity-bound lifecycle finalizer."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

TASK = "BEM949-DSM-1"
WORKFLOW = "dsm1-lifecycle-probe.yml"
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "governance/proofs/BEM949_dsm1_runtime_execution_receipt.json"
QUEUE = ROOT / "governance/roadmap/ACTIVE_QUEUE.json"

def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

p = argparse.ArgumentParser()
p.add_argument("--task-id", required=True)
p.add_argument("--trace-id", required=True)
p.add_argument("--workflow-id", required=True)
p.add_argument("--result", required=True)
a = p.parse_args()

if a.task_id != TASK:
    raise SystemExit("task_id_must_be_BEM949-DSM-1")
if a.workflow_id != WORKFLOW:
    raise SystemExit("workflow_id_must_be_dsm1-lifecycle-probe.yml")

result_path = Path(a.result)
state = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {
    "status": "BLOCKED", "task_id": TASK, "trace_id": a.trace_id,
    "result": {"blocker": "lifecycle_result_missing"},
}
if not isinstance(state, dict):
    raise SystemExit("lifecycle_result_not_object")
if state.get("task_id") not in (None, TASK):
    raise SystemExit("lifecycle_result_task_id_mismatch")
if state.get("trace_id") not in (None, a.trace_id):
    raise SystemExit("lifecycle_result_trace_id_mismatch")

detail = state.get("result") if isinstance(state.get("result"), dict) else {}
ok = (state.get("status") == "STATE_COMMITTED"
      and detail.get("terminal_state") == "COMPLETED"
      and detail.get("conclusion") == "success")
receipt = {
    "schema_version": 1, "protocol": "BEM-949", "task_id": TASK,
    "created_at": now(), "trace_id": a.trace_id,
    "status": "PASS" if ok else "BLOCKED",
    "runtime_execution_claim": ok,
    "evidence_kind": "github_actions_api_lifecycle_poll",
    "target_workflow": WORKFLOW, "lifecycle_result": detail,
    "acceptance": {
        "http_204_not_treated_as_completion": True,
        "dispatched_to_start_confirmed_to_terminal_observed": ok,
        "state_committed_recorded": ok,
        "task_identity_bound": True, "workflow_identity_bound": True,
        "trace_identity_bound": True,
    },
    "blockers": [] if ok else [str(detail.get("blocker", "lifecycle_not_completed"))],
}
save(OUT, receipt)
if ok:
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    task = next((x for x in queue.get("tasks", []) if x.get("id") == TASK), None)
    if not isinstance(task, dict):
        raise SystemExit("dsm1_queue_task_missing")
    task.update({
        "status": "DONE", "receipt": str(OUT.relative_to(ROOT)),
        "receipt_sha": hashlib.sha256(OUT.read_bytes()).hexdigest(),
        "receipt_sha_type": "sha256_content", "completed_at": now(),
        "trace_id": a.trace_id,
    })
    queue["current_task"] = None
    queue["updated_at"] = now()
    queue["version"] = int(queue.get("version", 0)) + 1
    save(QUEUE, queue)
print(json.dumps(receipt, ensure_ascii=False, indent=2))
raise SystemExit(0 if ok else 1)
