#!/usr/bin/env python3
"""BEM-949 P7 runtime release audit and queue reconciliation."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

STAGES = (
    "BEM949-P0.5-TEXT-INTEGRITY-FIX",
    "BEM949-P1-CI-STABILIZE",
    "BEM949-P2-FUNCTIONAL-RESTORE",
    "BEM949-P3-ALL-ROLE-E2E",
    "BEM949-P4-LIVE-LLM-FALLBACK",
    "BEM949-P5-RULE-ENFORCEMENT-COMPLETE",
    "BEM949-P6-LEARNING-LOOP-DRILL",
)
P6 = "BEM949-P6-LEARNING-LOOP-DRILL"
P7 = "BEM949-P7-RELEASE-AUDIT-FINAL"


def ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON object required: " + str(path))
    return value


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", default="governance/roadmap/ACTIVE_QUEUE.json")
    ap.add_argument(
        "--out",
        default="governance/proofs/BEM949_p7_external_release_audit_receipt.json",
    )
    ap.add_argument("--trace-id", default="bem949_p7_release_audit")
    args = ap.parse_args()

    queue_path = Path(args.queue)
    queue = read(queue_path)
    tasks = queue.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("ACTIVE_QUEUE.tasks must be a list")
    by_id = {x["id"]: x for x in tasks if isinstance(x, dict) and isinstance(x.get("id"), str)}
    if P6 not in by_id or P7 not in by_id:
        raise ValueError("P6 or P7 missing from ACTIVE_QUEUE")

    p6 = by_id[P6]
    p6_path = p6.get("receipt")
    if not isinstance(p6_path, str) or read(p6_path).get("status") != "PASS":
        raise ValueError("P6 receipt is not PASS")
    p6["status"] = "DONE"
    p6["completed_at"] = ts()
    p6["receipt_sha"] = sha(p6_path)
    p6["receipt_sha_type"] = "sha256_content"

    checks = []
    blockers = []
    for task_id in STAGES:
        task = by_id.get(task_id)
        if task is Noe:
            checks.append({"task_id": task_id, "clean_done": False, "reason": "missing_task"})
            blockers.append("missing_task:" + task_id)
            continue

        path = task.get("receipt")
        status = None
        error = None
        if isinstance(path, str) and Path(path).is_file():
            try:
                status = read(path).get("status")
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                error = type(exc).__name__
        else:
            error = "missing_receipt"
        clean = task.get("status") == "DONE" and status == "PASS"
        checks.append(
            {
                "task_id": task_id,
                "queue_status": task.get("status"),
                "receipt_status": status,
                "clean_done": clean,
                "error": error,
            }
        )
        if not clean:
            blockers.append(
                "not_clean_done:"
                + task_id
                + ":queue="
                + str(task.get("status"))
                + ":receipt="
                + str(status or error)
            )

    passed = not blockers
    runner_path = Path(__file__).resolve()
    receipt = {
        "schema_version": 1,
        "protocol": "BEM-949",
        "task_id": P7,
        "receipt_id": "BEM949_p7_external_release_audit",
        "created_at": ts(),
        "trace_id": args.trace_id,
        "evidence_kind": "independent_runtime_audit",
        "runtime_execution_claim": True,
        "execution": {
            "runner_path": "governance/runners/bem949_release_audit_runner.py",
            "runner_sha": sha(runner_path),
            "runner_sha_type": "sha256_content",
            "queue_sha": sha(queue_path),
            "queue_sha_type": "sha256_content",
        },
        "checks": checks,
        "blockers": blockers,
        "acceptance": {
            "all_p05_to_p6_clean_done": passed,
            "limitations_absent": passed,
            "broad_release_pass_claimed": passed,
        },
        "non_claim": "BLOCKED is an executed audit result, not a Release PASS.",
        "status": "PASS" if passed else "BLOCKED",
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    p7 = by_id[P7]
    p7["status"] = "DONE" if passed else "BLOCKED"
    p7["completed_at"] = ts()
    p7["receipt_sha"] = sha(out_path)
    p7["receipt_sha_type"] = "sha256_content"
    queue["current_task"] = None
    queue["queue_state"] = "COMPLETE" if passed else "BLOCKED"
    queue["system_status"] = "BEM949_RELEASE_AUDIT_PASS" if passed else "BEM949_RELEASE_AUDIT_BLOCKED"
    queue["release_status"] = "PASS" if passed else "VERIFIED_WITH_LIMITATIONS"
    queue["next_action"] = (
        "Roadmap complete." if passed
        else "Resume only recorded blockers; do not claim broad Release PASS."
    )
    queue["updated_at"] = ts()
    progress = queue.get("progress")
    if isinstance(progress, dict):
        done = sum(
            1 for task in tasks
            if isinstance(task, dict) and str(task.get("status", "")).startswith("DONE")
        )
        progress["tasks_done"] = done
        total = progress.get("tasks_total")
        if isinstance(total, int) and total:
            progress["percent"] = round(done * 100 / total, 2)
    queue_path.write_text(json.dumps(queue, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
