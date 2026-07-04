#!/usr/bin/env python3
"""Identity-bound DSM-1 lifecycle finalizer."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TASK_ID = "BEM949-DSM-1"
WORKFLOW_ID = "dsm1-lifecycle-probe.yml"
ROOT = Path(__file__).resolve().parents[2]
RUNTIME_RECEIPT = ROOT / "governance/proofs/BEM949_dsm1_runtime_execution_receipt.json"
QUEUE_PATH = ROOT / "governance/roadmap/ACTIVE_QUEUE.json"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_result(path: Path, trace_id: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "status": "BLOCKED",
            "task_id": TASK_ID,
            "trace_id": trace_id,
            "result": {"blocker": "lifecycle_result_missing"},
        }
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit("lifecycle_result_not_object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--workflow-id", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()

    if args.task_id != TASK_ID:
        raise SystemExit("task_id_must_be_BEM949-DSM-1")
    if args.workflow_id != WORKFLOW_ID:
        raise SystemExit("workflow_id_must_be_dsm1-lifecycle-probe.yml")

    lifecycle = read_result(Path(args.result), args.trace_id)
    if lifecycle.get("task_id") != TASK_ID:
        raise SystemExit("lifecycle_result_task_id_mismatch")
    if lifecycle.get("trace_id") != args.trace_id:
        raise SystemExit("lifecycle_result_trace_id_mismatch")

    detail = lifecycle.get("result")
    detail = detail if isinstance(detail, dict) else {}
    passed = (
        lifecycle.get("status") == "STATE_COMMITTED"
        and detail.get("termal_state") == "COMPLETED"
        and detail.get("conclusion") == "success"
    )
    recipt: dict[str, Any] = {
        "schema_version": 1,
        "protocol": "BEM-949",
        "task_id": TASK_ID,
        "created_at": now(),
        "trace_id": args.trace_id,
        "status": "PASS" if passed else "BLOCKED",
        "runtime_execution_claim": passed,
        "evidence_kind": "github_actions_api_lifecycle_poll",
        "target_workflow": WORKFLOW_ID,
        "lifecycle_result": detail,
        "acceptance": {
            "http_204_not_treated_as_completion": True,
            "dispatched_to_start_confirmed_to_terminal_observed": passed,
            "state_committed_recorded": passed,
            "task_identity_bound": True,
            "workflow_identity_bound": True,
            "trace_identity_bound": True,
        },
        "blockers": [] if passed else [
            str(detail.get("blocker", "lifecycle_not_completed"))
        ],
    }
    write_json(RUNTIME_RECEIPT, receipt)

    if not passed:
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return 1

    queue = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    task = next(
        (
            item for item in queue.get("tasks", [])
            if isinstance(item, dict) and item.get("id") == TASK_ID
        ),
        None,
    )
    if not isinstance(task, dict):
        raise SystemExit("dsm1_queue_task_missing")
    task.update(
        {
            "status": "DONE",
            "receipt": str(RUNTIME_RECEIPT.relative_to(ROOT)),
            "receipt_sha": hashlib.sha256(RUNTIME_RECEIPT.read_bytes()).hexdigest(),
            "receipt_sha_type": "sha256_content",
            "completed_at": now(),
            "trace_id": args.trace_id,
        }
    )
    queue.update(
        {
            "current_task": None,
            "queue_state": "READY",
            "updated_at": now(),
            "version": int(queue.get("version", 0)) + 1,
        }
    )
    write_json(QUEUE_PATH, queue)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
