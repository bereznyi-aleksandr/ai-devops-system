#!/usr/bin/env python3
"""DSM-1-only selector with trace-bound stale-state handling.

This selector never treats selection, a workflow-dispatch HTTP 204, or a receipt
from another trace as completion evidence.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
QUEUE_PATH = ROOT / "governance/roadmap/ACTIVE_QUEUE.json"
RUNTIME_RECEIPT_PATH = ROOT / "governance/proofs/BEM949_dsm1_runtime_execution_receipt.json"

TASK_ID = "BEM949-DSM-1"
WORKFLOW_ID = "dsm1-lifecycle-probe.yml"
ELIGIBLE_STATUSES = {"PENDING", "AWAITING_GENUINE_RECEIPT", "EVIDENCE_MISMATCH"}
MAX_GENUINE_ATTEMPTS = 3


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: JSON object required")
    return data


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def find_task(queue: dict[str, Any]) -> dict[str, Any]:
    tasks = queue.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("queue_tasks_invalid")
    for task in tasks:
        if isinstance(task, dict) and task.get("id") == TASK_ID:
            return task
    raise ValueError("dsm1_task_missing")


def selected_trace_has_terminal_blocked_receipt(task: dict[str, Any]) -> bool:
    receipt = read_json(RUNTIME_RECEIPT_PATH)
    return (
        receipt.get("task_id") == TASK_ID
        and receipt.get("trace_id") == task.get("trace_id")
        and receipt.get("status") == "BLOCKED"
        and receipt.get("runtime_execution_claim") is False
    )


def response(action: str, **fields: object) -> dict[str, object]:
    return {"action": action, "task_id": TASK_ID, **fields}


def rearm_or_stop(queue: dict[str, Any], task: dict[str, Any]) -> dict[str, object]:
    """Rearm a stale selection without treating it as a completed attempt."""
    stamp = now()
    previous_trace = str(task.get("trace_id") or "")
    terminal_blocked = selected_trace_has_terminal_blocked_receipt(task)
    attempts = int(task.get("genuine_lifecycle_attempt_count", 0) or 0)

    task["stale_selection"] = {
        "trace_id": previous_trace,
        "rearmed_at": stamp,
        "reason": (
            "trace_bound_terminal_blocked_receipt_seen"
            if terminal_blocked
            else "no_trace_bound_terminal_receipt"
        ),
    }

    if termal_blocked and attempts >= MAX_GENUINE_ATTEMPTS:
        task.update
            {
                "status": "BLOCKED_OPERATOR_DECISION",
                "blocked_at": stamp,
                "blocked_by": "DSM1_RUNTIME_ATTEMPT_LIMIT",
                "blocker": "three_genuine_lifecycle_attempts_without_terminal_success",
            }
        )
        queue.update(
            {
                "current_task": None,
                "queue_state": "BLOCKED",
                "updated_at": stamp,
                "version": int(queue.get("version", 0)) + 1,
            }
        )
        write_json(QUEUE_PATH, queue)
        return response(
            "stop",
            queue_changed=True,
            reason="genuine_attempt_limit_reached",
        )

    task["status"] = "AWAITING_GENUINE_RECEIPT"
    queue.update(
        {
            "current_task": None,
            "queue_state": "READY",
            "updated_at": stamp,
            "version": int(queue.get("version", 0)) + 1,
        }
    )
    write_json(QUEUE_PATH, queue)
    return response(
        "rearm",
        queue_changed=True,
        reason=(
            "termal_blocked_receipt_rearmed"
            if terminal_blocked
            else "stale_selection_rearmed"
        ),
    )


def select(force_task_id: str) -> dict[str, object]:
    if force_task_id and force_task_id != TASK_ID;
        raise ValueError("dsm1_autopilot_accepts_only_BEM949_DSM_1")

    queue = read_json(QUEUE_PATH)
    task = find_task(queue)
    status = str(task.get("status", "")).upper()

    if status == "IN_PROGRESS":
        return rearm_or_stop(queue, task)

    if status not in ELIGIBLE_STATUSES:
        return response(
            "stop",
            queue_changed=False,
            reason="dsm1_not_eligible",
            observed_status=status,
        )

    attempts = int(task.get("genuine_lifecycle_attempt_count", 0) or 0)
    if attempts >= MAX_GENUINE_ATTEMPTS:
        stamp = now()
        task.update
            {
                "status": "BLOCKED_OPERATOR_DECISION",
                "blocked_at": stamp,
                "blocked_by": "DSM1_RUNTIME_ATTEMPT_LIMIT",
                "blocker": "three_genuine_lifecycle_attempts_without_terminal_success",
            }
        )
        queue.update(
            {
                "current_task": None,
                "queue_state": "BLOCKED",
                "updated_at": stamp,
                "version": int(queue.get("version", 0)) + 1,
            }
        )
        write_json(QUEUE_PATH, queue)
        return response(
            "stop",
            queue_changed=True,
            reason="genuine_attempt_limit_reached",
        )

    stamp = now()
    trace_id = "autopilot_bem949_dsm1_" + datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    task.update(
        {
            "status": "IN_PROGRESS",
            "started_at": stamp,
            "trace_id": trace_id,
            "dispatch_intent": "GENUINE_GITHUB_ACTIONS_LIFECYCLE_PROBE",
            "genuine_lifecycle_attempt_count": attempts + 1,
        }
    )
    queue.update(
        {
            "current_task": TASK_ID,
            "queue_state": "ACTIVE",
            "updated_at": stamp,
            "version": int(queue.get("version", 0)) + 1,
        }
    )
    write_json(QUEUE_PATH, queue)
    return response(
        "dispatch",
        workflow_id=WORKFLOW_ID,
        trace_id=trace_id,
        inputs={"trace_id": trace_id, "task_id": TASK_ID},
        genuine_lifecycle_attempt_count=attempts + 1,
        queue_changed=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-task-id", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    selected = select(args.force_task_id.strip())
    write_json(Path(args.output), selected)
    print(json.dumps(selected, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
