#!/usr/bin/env python3
"""BEM-949 P7 independent release-audit runner.

The runner reads roadmap state and its referenced receipts. It emits PASS only
when every P0.5-P6 stage is completed without a recorded limitation or blocker.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_STAGE_IDS = (
    "BEM949-P0.5-TEXT-INTEGRITY-FIX",
    "BEM949-P1-CI-STABILIZE",
    "BEM949-P2-FUNCTIONAL-RESTORE",
    "BEM949-P3-ALL-ROLE-E2E",
    "BEM949-P4-LIVE-LLM-FALLBACK",
    "BEM949-P5-RULE-ENFORCEMENT-COMPLETE",
    "BEM949-P6-LEARNING-LOOP-DRILL",
)
DONE_STATUSES = {"DONE"}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"object_required:{path}")
    return payload


def build_receipt(queue_path: Path, trace_id: str) -> dict[str, Any]:
    queue = load_json(queue_path)
    tasks = queue.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("queue_tasks_not_list")

    by_id = {
        str(task.get("id")): task
        for task in tasks
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    }
    runner_path = Path(__file__).resolve()
    checks: list[dict[str, Any]] = []
    blockers: list[str] = []

    for task_id in REQUIRED_STAGE_IDS:
        task = by_id.get(task_id)
        if task is None:
            checks.append({"task_id": task_id, "present": False})
            blockers.append(f"missing_task:{task_id}")
            continue

        status = str(task.get("status", ""))
        receipt_path_raw = task.get("receipt")
        receipt_exists = isinstance(receipt_path_raw, str) and Path(receipt_path_raw).is_file()
        receipt_status = None
        receipt_sha = None
        if receipt_exists:
            receipt_path = Path(receipt_path_raw)
            receipt_sha = sha256_file(receipt_path)
            try:
                receipt_status = load_json(receipt_path).get("status")
            except (OSError, json.JSONDecodeError, ValueError):
                receipt_status = "UNREADABLE"

        clean_done = status in DONE_STATUSES and receipt_status == "PASS"
        checks.append(
            {
                "task_id": task_id,
                "queue_status": status,
                "receipt_path": receipt_path_raw,
                "receipt_exists": receipt_exists,
                "receipt_status": receipt_status,
                "receipt_sha": receipt_sha,
                "receipt_sha_type": "sha256_content" if receipt_sha else None,
                "clean_done": clean_done,
            }
        )
        if not clean_done:
            blockers.append(f"stage_not_clean_done:{task_id}:{tatus}:{receipt_status}")

    broad_pass = not blockers
    return {
        "schema_version": 1,
        "protocol": "BEM-949",
        "task_id": "BEM949-P7-RELEASE-AUDIT-FINAL",
        "receipt_id": "BEM949_p7_external_release_audit",
        "created_at": utc_now(),
        "trace_id": trace_id,
        "evidence_kind": "independent_runtime_audit",
        "runtime_execution_claim": True,
        "execution": {
            "executed_at": utc_now(),
            "runner_path": "governance/runners/bem949_release_audit_runner.py",
            "runner_sha": sha256_file(runner_path),
            "runner_sha_type": "sha256_content",
            "queue_path": str(queue_path),
            "queue_sha": sha256_file(queue_path),
            "queue_sha_type": "sha256_content",
        },
        "checks": checks,
        "acceptance": {
            "all_p05_to_p6_clean_done": broad_pass,
            "broad_release_pass_claimed": broad_pass,
            "limitations_absent": broad_pass,
        },
        "blockers": blockers,
        "non_claim": (
            "A BLOCKED audit is a completed audit observation, not a release PASS. "
            "This receipt does not de-claim or override the underlying stage evidence."
        ),
        "status": "PASS" if broad_pass else "BLOCKED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--queue",
        default="governance/roadmap/ACTIVE_QUEUE.json",
    )
    parser.add_argument(
        "--out",
        default="governance/proofs/BEM949_p7_external_release_audit_receipt.json",
    )
    parser.add_argument("--trace-id", default="bem949_p7_release_audit")
    args = parser.parse_args()

    receipt = build_receipt(Path(args.queue), args.trace_id)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
