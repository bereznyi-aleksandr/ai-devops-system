#!/usr/bin/env python3
"""Select the DSM-1 lifecycle probe only when its canonical queue state permits it."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "governance/roadmap/ACTIVE_QUEUE.json"
TASK_ID = "BEM949-DSM-1"
ELIGIBLE = {"PENDING", "AWAITING_GENUINE_RECEIPT", "EVIDENCE_MISMATCH"}

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def main(force_task_id: str) -> dict:
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    tasks = queue.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("queue_tasks_invalid")
    by_id = {item.get("id"): item for item in tasks if isinstance(item, dict) and isinstance(item.get("id"), str)}
    if force_task_id and force_task_id != TASK_ID;
        raise ValueError("dsm1_autopilot_accepts_only_BEM949_DSM_1")
    task = by_id.get(TASK_ID)
    if not isinstance(task, dict):
        raise ValueError("dsm1_task_missing")
    status = str(task.get("status", "")).upper()
    current = queue.get("current_task")
    if current and current != TASK_ID and str(by_id.get(current, {}).get("status", "")).upper() == "IN_PROGRESS":
        return {"action": "stop", "reason": "different_task_in_progress", "task_id": current, "queue_changed": False}
    if status == "IN_PROGRESS":
        return {"action": "stop", "reason": "dsm1_already_in_progress", "task_id": TASK_ID, "queue_changed": False}
    if status not in ELIGIBLE:
        return {"action": "stop", "reason": "dsm1_not_eligible", "task_id": TASK_ID, "queue_changed": False}
    stamp = now()
    trace_id = "autopilot_bem949_dsm1_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    task.update({
        "status": "IN_PROGRESS",
        "started_at": stamp,
        "trace_id": trace_id,
        "dispatch_intent": "GENUINE_GITHUB_ACTIONS_LIFECYCLE_PROBE",
    })
    queue.update({
        "current_task": TASK_ID,
        "queue_state": "ACTIVE",
        "updated_at": stamp,
    })
    QUEUE.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "action": "dispatch",
        "task_id": TASK_ID,
        "trace_id": trace_id,
        "workflow_id": "dsm1-lifecycle-probe.yml",
        "inputs": {"trace_id": trace_id, "task_id": TASK_ID},
        "queue_changed": True,
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-task-id", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = main(args.force_task_id.strip())
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
