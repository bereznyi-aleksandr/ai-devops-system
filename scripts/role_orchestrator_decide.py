#!/usr/bin/env python3
import json
import os
from pathlib import Path

cycle_id = os.environ.get("CYCLE_ID", "")
transport = Path("governance/transport/results.jsonl")
state_path = Path("governance/state/role_cycle_state.json")
records = []
task_type = None
if transport.exists():
    for line in transport.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("cycle_id") == cycle_id:
            records.append(rec)
            if rec.get("record_type") == "curator_intake" and rec.get("task_type"):
                task_type = rec.get("task_type")

latest = records[-1] if records else {"record_type": "none", "status": "failed"}
status = latest.get("status")
record_type = latest.get("record_type")
next_role = "curator"
reason = "default_to_curator"
blocker = None

if status in ["failed", "cancelled", "timeout"]:
    reason = "upstream_blocker"
    blocker = {"code": "UPSTREAM_ROLE_FAILED", "latest_record_type": record_type}
elif record_type == "curator_assignment":
    if task_type == "development":
        next_role = "analyst"
        reason = "curator_assigned_development_task_to_orchestrator"
    elif task_type == "audit":
        next_role = "auditor"
        reason = "curator_assigned_audit_task_to_orchestrator"
    elif task_type == "hotfix":
        next_role = "auditor"
        reason = "curator_assigned_hotfix_to_auditor_first"
elif record_type == "analysis" and status == "completed":
    next_role = "auditor"
    reason = "analysis_completed_requires_audit"
elif record_type == "audit" and latest.get("decision") == "PASS_TO_EXECUTOR":
    next_role = "executor"
    reason = "audit_pass_to_executor"
elif record_type == "execution" and status == "completed":
    next_role = "auditor_final"
    reason = "execution_completed_requires_final_audit"
elif record_type == "audit" and latest.get("decision") == "FINAL_PASS":
    next_role = "curator_closure"
    reason = "final_audit_pass_returns_to_curator"

decision = "route_to_" + next_role
out = {
    "record_type": "role_orchestrator_decision",
    "cycle_id": cycle_id,
    "source": "role-orchestrator.yml",
    "from_role": "role_orchestrator",
    "to_role": next_role,
    "status": "completed" if blocker is None else "blocked",
    "decision": decision,
    "reason": reason,
    "input_record_type": record_type,
    "artifact_path": "governance/transport/results.jsonl",
    "commit_sha": None,
    "blocker": blocker,
    "created_at": "workflow_runtime"
}
transport.parent.mkdir(parents=True, exist_ok=True)
with transport.open("a", encoding="utf-8") as f:
    f.write(json.dumps(out, ensure_ascii=False) + "
")
state = {}
if state_path.exists():
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        state = {}
state["cycle_id"] = cycle_id
state["active_role"] = "role_orchestrator"
state["next_role"] = next_role
state["last_orchestrator_decision"] = out
state["blocker"] = blocker
state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "
", encoding="utf-8")
