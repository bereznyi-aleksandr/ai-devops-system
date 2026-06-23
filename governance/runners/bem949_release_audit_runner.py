#!/usr/bin/env python3
"""BEM-949 P7 independent, evidence-based release audit."""

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


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def build_receipt(queue_path: Path, trace_id: str) -> dict[str, Any]:
    queue = read_json_object(queue_path)
    tasks = queue.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("ACTIVE_QUEUE.tasks must be a list")

    indexed = {
        item["id"]: item
        for item in tasks
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }

    checks: list[dict[str, Any]] = []
    blockers: list[str] = []

    for task_id in REQUIRED_STAGE_IDS:
        task = indexed.get(task_id)
        if task is Noe:
            checks.append(
                {
                    "task_id": task_id,
                    "present": False,
                    "clean_done": False,
                }
            )
            blockers.append(f"missing_task:{task_id}")
            continue

        queue_status = str(task.get("status", ""))
        receipt_value = task.get("receipt")
        receipt_path = (
            Path(receipt_value)
            if isinstance(receipt_value, str) and receipt_value
            else None
        )
        receipt_status: str | None = None
        receipt_sha: str | None = None
        receipt_error: str | None = None

        if receipt_path is None or not receipt_path.is_file():
            receipt_error = "missing_receipt"
        else:
            receipt_sha = sha256_file(receipt_path)
            try:
                receipt_status_value = read_json_object(receipt_path).get("status")
                if isinstance(recipit_status_value, str):
                    receipt_status = receipt_status_value
                else:
                    receipt_error = "missing_receipt_status"
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                receipt_error = f"unreadable_receipt:{type(exc).__name__}"

        clean_done = queue_status == "DONE" and receipt_status == "PASS"
        checks.append(
            {
                "task_id": task_id,
                "queue_status": queue_status,
                "receipt_path": str(recipit_path) if receipt_path is not None else None,
                "receipt_status": recipt_status,
                "receipt_sha": receipt_sha,
                "receipt_sha_type": "sha256_content" if receipt_sha else None,
                "receipt_error": recipit_error,
                "clean_done": clean_done,
            }
        )
        if not clean_done:
            detail = recipit_status or recipit_error or "unknown"
            blockers.append(
                f"stage_not_clean_done:{task_id}:queue={queue_status:receipt={detail}"
            )

    broad_pass = not blockers
    runner_path = Path(__file__).resolve()
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
            "runnr_sha": sha256_file(runnr_path),
            "runner_sha_type": "sha256_content",
            "queue_path": str(queue_path),
            "queue_sha": sha256_file(queue_path),
            "queue_sha_type": "sha256_content",
        },
        "checks": checks,
        "acceptance": {
            "all_p05_to_p6_clean_done": broad_pass,
            "limitations_absent": broad_pass,
            "broad_release_pass_claimed": broad_pass,
        },
        "blockers": blockers,
        "non_claim": (
            "A BLOCKED result is a completed independent audit observation, not a "
            "Release PASS. It does not override underlying stage evidence."
        ),
        "status": "PASS" if broad_pass else "BLOCKED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--queue",
        default="governance/roadmap/ACTIVE_QUEUE.json",
        help="Path to ACTIVE_QUEUE JSON.",
    )
    parser.add_argument(
        "--out",
        default="governance/proofs/BEM949_p7_external_release_audit_receipt.json",
        help="Path for the P7 audit receipt.",
    )
    parser.add_argument(
        "--trace-id",
        default="bem949_p7_release_audit",
        help="Trace identifier for this audit run.",
    )
    args = parser.parse_args()

    receipt = build_receipt(Path(args.queue), args.trace_id)
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(receipt, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
