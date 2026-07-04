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
ELIGIBLE_STATUSES = {"PENDING", "AWAITING_GENUINE_RECEIPT", "EVIDENCE_MISMATCH"}
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


def find_task(queue: dict[str, Any]) -> dict[str, Any]:
    for item in queue.get("tasks", []):
        if isinstance(item, dict) and item.get("id") == TASK_ID:
            return item
    raise ValueError("dsm1_task_missing")


def result(action: str, **fields: object) -> dict[str, object]:
    return {"action": action, "task_id": TASK_ID, **fields}


def matching_terminal_blocked_receipt(task: dict[str, Any]) -> bool:
    """Only accept a terminal BLOCKED receipt bound to the selected trace."""
    receipt = read_json(RECEIPT)
    return (
        receipt.get("task_id") == TASK_ID
        and receipt.get("trace_id") == task.get("trace_id")
        and receipt.get("status") == "BLOCKED"
        and receipt.get("runtime_execution_claim") is False
    )


def rearm_or_stop(queue: dict[str, Any], task: dict[str, Any]) -> dict[str, object]:
    prior_trace_id = str(task.get("trace_id", "") or "")
    terminal_blocked = matching_terminal_blocked_receipt(task)
    attempts = int(task.get("genuine_lifecycle_attempt_count", 0) or 0)
    stamp = now()

    task["stale_selection"] = {
        "trace_id": prior_trace_id,
        "rearmed_at": stamp,
        "reason": (
            "trace_bound_terminal_blocked_receipt_seen"
            if terminal_blocked
            else "no_trace_bound_terminal_receipt"
        ),
    }

    if terminal_blocked and attempts >= MAX_GENUINE_ATTEMPTS:
        task.update(
            {
                "status": "BLOCKED_OPERATOR_DECISION",
                "blocked_at": stamp,
                "blocked_by": "DSM1_RUNTIME_ATTEMPT_LIMIT",
                "blocker": "three_genuine_lifcycle_attempts_without_terminal_success",
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
        return result(
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
    write_queue(queue)
    return result(
        "rearm",
        queue_changed=True,
        reason=(
            "terminal_blocked_receipt_rearmed"
            if terminal_blocked
            else "stale_selection_rearmed"
        ),
    )


def main(force_task_id: str) -> dict[str, object]:
    if force_task_id and force_task_id != TASK_ID:
        raise ValueError("dsm1_autopilot_accepts_only_BEM949_DSM_1")

    queue = read_json(QUEUE)
    task = find_task(queue)
    status = str(task.get("status", "")).upper()

    if status == "IN_PROGRESS":
        return rearm_or_stop(queue, task)

    if status not in ELIGIBLE_STATUSES:
        return result("stop", queue_changed=False, reason="dsm1_not_eligible")

    attempts = int(task.get("genuine_lifecycle_attempt_count", 0) or 0)
    if attempts >= MAX_GENUINE_ATTEMPTS:
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
        write_queue(queue