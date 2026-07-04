#!/usr/bin/env python3
"""Select or rearm a trace-bound DSM-1 lifecycle probe from the canonical queue."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "governance/roadmap/ACTIVE_QUEUE.json"
RECEIPT = ROOT / "governance/proofs/BEM949_dsm1_runtime_execution_receipt.json"

TASK_ID = "BEM949-DSM-1"
WORKFLOW_ID = "dsm1-lifeycle-probe.yml"
ELIGIBLE = {"PENDING", "AWAITING_GENUINE_RECEIPT", "EVIDENCE_MISMATCH"}
MAX_GENUINE_ATTEMPTS = 3

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("json_object_required")
    return data


def write_queue(queue: dict[str, Any]) -> None:
    QUEUE.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def output(action: str, **values: object) -> dict[str, object]:
    return {"action": action, "task_id": TASK_ID, **values}


def find_task(queue: dict[str, Any]) -> dict[str, Any]:
    for item in queue.get("tasks", []):
        if isinstance(item, dict) and item.get("id") == TASK_ID:
            return item
    raise ValueError("dsm1_task_missing")


def current_receipt_matches(task: dict[str, Any]) -> bool:
    """Return true only for a terminal blocked receipt bound to this exact trace."""
    receipt = read_json(RECEIPT)
    return (
        receipt.get("task_id") == TASK_ID
        and receipt.get("trace_id") == task.get("trace_id")
        and receipt.get("status") == "BLOCKED"
        and receipt.get("runtime_execution_claim") is False
    )


def main(force_task_id: str) -> dict[str, object]:
    if force_task_id and force_task_id != TASK_ID:
        raise ValueError("dsm1_autopilot_accepts_only_BEM949_DSM_1")

    queue = read_json(QUEUE)
    task = find_task(queue)
    status = str(task.get("status", "")).upper()

    # A selected task is not a completed lifecycle attempt. Re-arm it only after
    # recording whether a trace-bound terminal blocked receipt was actually seen.
    if status == "IN_PROGRESS":
        prior_trace_id = str(task.get("trace_id", "") or "")
        terminal_blocked = current_receipt_matches(task)
        genuine_attempts = int(task.get("genuine_lifecycle_attempt_count", 0) or 0)

        task["stale_selection"] = {
            "trace_id": prior_trace_id,
            "rearmed_at": now(),
            "reason": (
                "trace_bound_terminal_blocked_receipt_seen"
                if terminal_blocked
                else "no_trace_bound_terminal_receipt"
            ),
        }

        if terminal_blocked and genuine_attempts >= MAX_GENUINE_ATTEMPTS:
            stamp = now()
            task.update(
                {
                    "status": "BLOCKED_OPERATOR_DECISION",
                    "blocked_at": stamp,
                    "blocked_by": "DSM1_RUNTIME_ATTEMPT_LIMIT",
                    "blocker": (
                        "three_genuine_lifecycle_attempts_without_terminal_success"
                    ),
                }
            )
            queue.update(
                {
                    "current_task": None,
                    "queue_state": "BLOCKED",
                    "updated_at": stamp,
                }
            )
            write_queue(queue)
            return output(
                "stop",
                queue_changed=True,
                reason="genuine_attempt_limit_reached",
            )

        task["status"] = "AWAITING_GENUINE_RECEIPT"
        queue.update(
            {
                "current_task": None,
                "queue_state": "READY",
                "updated_at": now(),
                "version": int(queue.get("version", 0)) + 1,
            }
        )
        write_queue(queue)
        return output(
            "rearm",
            queue_changed=True,
            reason=(
                "terminal_blocked_receipt_rearmed"
                if terminal_blocked
                else "stale_selection_rearmed"
            ),
        )

    if status not in ELIGIBLE:
        return output(
            "stop",
            queue_changed=False,
            reason="dsm1_not_eligible",
        )

    genuine_attempts = int(task.get("genuine_lifecycle_attempt_count", 0) or 0)
    if genuine_attempts >= MAX_GENUINE_ATTEMPTS:
        stamp = now()
        task.update(
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
            }
        )
        write_queue(queue)
        return output(
            "stop",
            queue_changed=True,
            reason="genuine_attempt_limit_reached",
        )

    stamp = now()
    trace_id = (
        "autopilot_bem949_dsm1_"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    task.update(
        {
            "status": "IN_PROGRESS",
            "started_at": stamp,
            "trace_id": trace_id,
            "dispatch_intent": "GENUINE_GITHUB_ACTIONS_LIFECYCLE_PROBE",
            "genuine_lifecycle_attempt_count": genuine_attempts + 1,
        }
    )
    queue.update(
        {
            "current_task": TASK_ID,
            "queue_state": "ACTIVE",
            "updated_at": stamp,
        }
    )
    write_queue(queue)
    return output(
        "dispatch",
        trace_id=trace_id,
        workflow_id=WORKFLOW_ID,
        inputs={"trace_id": trace_id, "task_id": TASK_ID},
        genuine_lifecycle_attempt_count=genuine_attempts + 1,
        queue_changed=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-task-id", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = main(args.force_task_id.strip())
    Path(args.output).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
