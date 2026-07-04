#!/usr/bin/env python3
"""Select a genuine, trace-bound DSM-1 lifecycle probe."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "governance/roadmap/ACTIVE_QUEUE.json"
TASK = "BEM949-DSM-1"
ELIGIBLE = {"PENDING", "AWAITING_GENUINE_RECEIPT", "EVIDENCE_MISMATCH"}

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def select(force_task_id: str) -> dict:
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    tasks = queue.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("queue_tasks_invalid")
    items = {x.get("id"): x for x in tasks if isinstance(x, dict) and isinstance(x.get("id"), str)}
    if force_task_id and force_task_id != TASK:
        raise ValueError("dsm1_autopilot_accepts_only_BEM949-DSM-1")
    task = items.get(TASK)
    if not isinstance(task, dict):
        raise ValueError("dsm1_task_missing")
    current = queue.get("current_task")
    if current and current != TASK and str(items.get(current, {}).get("status", "")).upper() == "IN_PROGRESS":
        return {"action": "stop", "reason": "different_task_in_progress", "task_id": current, "queue_changed": False}
    status = str(task.get("status", "")).upper()
    if status == "IN_PROGRESS":
        return {"action": "stop", "reason": "dsm1_already_in_progress", "task_id": TASK, "queue_changed": False}
    if status not in ELIGIBLE:
        return {"action": "stop", "reason": "dsm1_not_eligible", "task_id": TASK, "queue_changed": False}
    stamp = now()
    trace = "autopilot_bem949_dsm1_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    task.update({"status": "IN_PROGRESS", "started_at": stamp, "trace_id": trace, "dispatch_intent": "GENUINE_GITHUB_ACTIONS_LIFECYCLE_PROBE"})
    queue.update({"current_task": TASK, "queue_state": "ACTIVE", "updated_at": stamp})
    QUEUE.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"action": "dispatch", "task_id": TASK, "trace_id": trace, "workflow_id": "dsm1-lifecycle-probe.yml",
            "inputs": {"trace_id": trace, "task_id": TASK}, "queue_changed": True}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-task-id", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = select(args.force_task_id.strip())
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
