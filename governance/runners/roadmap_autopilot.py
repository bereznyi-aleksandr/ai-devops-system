#!/usr/bin/env python3
"""DSM-1-only selector with trace-bound stale-state handling."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "governance/roadmap/ACTIVE_QUEUE.json"
RECEIPT = ROOT / "governance/proofs/BEM949_dsm1_runtime_execution_receipt.json"
TASK_ID = "BEM949-DSM-1"
WORKFLOW_ID = "dsm1-lifecycle-probe.yml"
ELIGIBLE = {"PENDING", "AWAITING_GENUINE_RECEIPT", "EVIDENCE_MISMATCH"}
MAX_ATTEMPTS = 3

def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def load(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def task_for(queue):
    for item in queue.get("tasks", []):
        if isinstance(item, dict) and item.get("id") == TASK_ID:
            return item
    raise ValueError("dsm1_task_missing")

def terminal_blocked(task):
    receipt = load(RECEIPT)
    return (
        receipt.get("task_id") == TASK_ID
        and receipt.get("trace_id") == task.get("trace_id")
        and receipt.get("status") == "BLOCKED"
        and receipt.get("runtime_execution_claim") is False
    )

def emit(action, **values):
    return {"action": action, "task_id": TASK_ID, **values}

def main(force_task_id):
    if force_task_id and force_task_id != TASK_ID:
        raise ValueError("dsm1_autopilot_accepts_only_BEM949_DSM_1")
    queue = load(QUEUE)
    task = task_for(queue)
    status = str(task.get("status", "")).upper()
    attempts = int(task.get("genuine_lifecycle_attempt_count", 0) or 0)

    if status == "IN_PROGRESS":
        stamp = now()
        blocked = terminal_blocked(task)
        task["stale_selection"] = {
            "trace_id": task.get("trace_id", ""),
            "rearmed_at": stamp,
            "reason": "terminal_blocked_receipt_seen" if blocked else "no_terminal_receipt",
        }
        if blocked and attempts >= MAX_ATTEMPTS:
            task.update({"status": "BLOCKED_OPERATOR_DECISION", "blocked_at": stamp,
                         "blocker": "three_genuine_lifecycle_attempts_without_terminal_success"})
            queue.update({"current_task": None, "queue_state": "BLOCKED", "updated_at": stamp})
            save(QUEUE, queue)
            return emit("stop", queue_changed=True, reason="genuine_attempt_limit_reached")
        task["status"] = "AWAITING_GENUINE_RECEIPT"
        queue.update({"current_task": None, "queue_state": "READY", "updated_at": stamp,
                      "version": int(queue.get("version", 0)) + 1})
        save(QUEUE, queue)
        return emit("rearm", queue_changed=True,
                    reason="terminal_blocked_receipt_rearmed" if blocked else "stale_selection_rearmed")

    if status not in ELIGIBLE:
        return emit("stop", queue_changed=False, reason="dsm1_not_eligible")
    if attempts >= MAX_ATTEMPTS:
        stamp = now()
        task.update({"status": "BLOCKED_OPERATOR_DECISION", "blocked_at": stamp,
                     "blocker": "three_genuine_lifecycle_attempts_without_terminal_success"})
        queue.update({"current_task": None, "queue_state": "BLOCKED", "updated_at": stamp})
        save(QUEUE, queue)
        return emit("stop", queue_changed=True, reason="genuine_attempt_limit_reached")

    stamp = now()
    trace_id = "autopilot_bem949_dsm1_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    task.update({"status": "IN_PROGRESS", "started_at": stamp, "trace_id": trace_id,
                 "dispatch_intent": "GENUINE_GITHUB_ACTIONS_LIFECYCLE_PROBE",
                 "genuine_lifecycle_attempt_count": attempts + 1})
    queue.update({"current_task": TASK_ID, "queue_state": "ACTIVE", "updated_at": stamp})
    save(QUEUE, queue)
    return emit("dispatch", trace_id=trace_id, workflow_id=WORKFLOW_ID,
                inputs={"trace_id": trace_id, "task_id": TASK_ID},
                genuine_lifecycle_attempt_count=attempts + 1, queue_changed=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-task-id", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    value = main(args.force_task_id.strip())
    save(Path(args.output), value)
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
