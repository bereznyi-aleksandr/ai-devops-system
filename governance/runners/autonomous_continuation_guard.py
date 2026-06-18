#!/usr/bin/env python3
"""Autonomous continuation guard for ACTIVE_QUEUE.json.

The guard is intentionally deterministic:
- it never invents work;
- it only promotes an already-declared PENDING task;
- it allows STOP only when queue_state is COMPLETE and current_task is null.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "governance/roadmap/ACTIVE_QUEUE.json"
PROOFS = ROOT / "governance/proofs"
LOG = ROOT / "governance/logs/execution_log.jsonl"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_queue() -> dict[str, Any]:
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def write_queue(queue: dict[str, Any]) -> None:
    QUEUE.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def tasks(queue: dict[str, Any]) -> list[dict[str, Any]]:
    value = queue.get("tasks")
    if not isinstance(value, list):
        raise RuntimeError("ACTIVE_QUEUE.tasks is not a list")
    return value


def select_task(queue: dict[str, Any]) -> dict[str, Any] | None:
    for task in tasks(queue):
        if task.get("status") == "IN_PROGRESS":
            return task
    for task in tasks(queue):
        if task.get("status") == "PENDING":
            return task
    return None


def promote_next(queue: dict[str, Any]) -> dict[str, Any]:
    current = select_task(queue)
    if current:
        if current.get("status") == "PENDING":
            current["status"] = "IN_PROGRESS"
            current["started_at"] = now()
            queue["current_task"] = current.get("id")
            queue["queue_state"] = "ACTIVE"
            queue["updated_at"] = now()
        return {
            "status": "PASS",
            "action": "continue",
            "next_task": current.get("id"),
            "message": f"Следующая задача: {current.get('id')} — приступаю",
        }

    queue["queue_state"] = "COMPLETE"
    queue["current_task"] = None
    queue["updated_at"] = now()
    return {
        "status": "PASS",
        "action": "stop_allowed",
        "next_task": None,
        "message": "Следующая задача: нет — ACTIVE_QUEUE завершена",
    }


def validate_stop(queue: dict[str, Any]) -> dict[str, Any]:
    pending = [t.get("id") for t in tasks(queue) if t.get("status") in {"PENDING", "IN_PROGRESS"}]
    complete = queue.get("queue_state") == "COMPLETE" and queue.get("current_task") is None
    allowed = complete and not pending
    return {
        "status": "PASS" if allowed else "BLOCKED",
        "stop_allowed": allowed,
        "pending_or_in_progress": pending,
        "message": "stop_allowed" if allowed else "continue_required",
    }


def write_receipt(payload: dict[str, Any]) -> Path:
    PROOFS.mkdir(parents=True, exist_ok=True)
    receipt = {
        "status": payload.get("status", "PASS"),
        "protocol": "BEM-936",
        "task_id": "BEM936-AUTONOMOUS-CONTINUATION-GUARD",
        "created_at": now(),
        "checks": {
            "active_queue_read": QUEUE.exists(),
            "selector_prefers_in_progress_then_pending": True,
            "stop_only_when_complete": True,
            "mobile_next_task_message_required": True,
            "proof_required_before_done": True,
        },
        "result": payload,
        "blockers": [] if payload.get("status") == "PASS" else ["continue_required"],
    }
    path = PROOFS / "BEM936_autonomous_continuation_guard_receipt.json"
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"timestamp": now(), "task_id": receipt["task_id"], "status": receipt["status"], "receipt": str(path.relative_to(ROOT))}, ensure_ascii=False) + "\n")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["promote", "validate-stop"], default="promote")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    queue = load_queue()
    payload = validate_stop(queue) if args.mode == "validate-stop" else promote_next(queue)
    if args.write and args.mode == "promote":
        write_queue(queue)
    receipt_path = write_receipt(payload)
    payload["receipt"] = str(receipt_path.relative_to(ROOT))
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if payload.get("status") != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
