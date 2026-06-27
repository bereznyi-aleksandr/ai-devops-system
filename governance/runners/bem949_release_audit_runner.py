#!/usr/bin/env python3
"""BEM-949 P7 runtime audit.

This runner emits an independent audit receipt.  A narrowly allowlisted
operator skip is non-blocking for the named P4 task only; it never becomes a
broad-release PASS by itself.
"""
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
P6 = STAGES[-1]
P7 = "BEM949-P7-RELEASE-AUDIT-FINAL"
OPERATOR_SKIPPED = {"BEM949-P4-LIVE-LLM-FALLBACK"}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def sha256_content(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt_status(receipt_path: object) -> tuple[str | None, str | None, str | None]:
    if not isinstance(receipt_path, str) or not receipt_path:
        return None, None, "missing_receipt_path"

    path = Path(receipt_path)
    if not path.is_file():
        return None, None, "missing_receipt"

    try:
        status = load_json_object(path).get("status")
    except Exception as exc:  # receipt parsing must produce an auditable result
        return None, None, f"unreadable:{type(exc).__name__}"

    if not isinstance(status, str):
        return None, sha256_content(path), "missing_receipt_status"
    return status, sha256_content(path), None


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
    parser.add_argument(
        "--trace-id",
        default="bem949_p7_release_audit",
    )
    args = parser.parse_args()

    queue_path = Path(args.queue)
    queue = load_json_object(queue_path)
    tasks = queue.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("ACTIVE_QUEUE.tasks must be a list")

    by_id = {
        task.get("id"): task
        for task in tasks
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    }
    if P6 not in by_id or P7 not in by_id:
        raise ValueError("P6 or P7 task missing")

    p6_status, p6_sha, p6_error = receipt_status(by_id[P6].get("receipt"))
    if p6_status != "PASS":
        raise ValueError(f"P6 receipt is not PASS: {p6_status or p6_error}")
    by_id[P6].update(
        status="DONE",
        completed_at=now(),
        receipt_sha=p6_sha,
        receipt_sha_type="sha256_content",
    )

    checks: list[dict] = []
    blockers: list[str] = []
    operator_skip_acknowledged: list[str] = []

    for task_id in STAGES:
        task = by_id.get(task_id)
        if task is None:
            checks.append(
                {
                    "task_id": task_id,
                    "clean_done": False,
                    "reason": "missing_task",
                }
            )
            blockers.append(f"missing_task:{task_id}")
            continue

        observed_receipt_status, receipt_sha, receipt_error = receipt_status(
            task.get("receipt")
        )
        queue_status = str(task.get("status", ""))
        is_allowed_operator_skip = (
            queue_status == "SKIPPED_BY_OPERATOR" and task_id in OPERATOR_SKIPPED
        )
        clean_done = (
            queue_status == "DONE" and observed_receipt_status == "PASS"
        ) or is_allowed_operator_skip

        if is_allowed_operator_skip:
            operator_skip_acknowledged.append(task_id)

        checks.append(
            {
                "task_id": task_id,
                "queue_status": queue_status,
                "receipt_status": observed_receipt_status,
                "receipt_sha": receipt_sha,
                "receipt_sha_type": "sha256_content" if receipt_sha else None,
                "receipt_error": receipt_error,
                "operator_skip_acknowledged": is_allowed_operator_skip,
                "clean_done": clean_done,
            }
        )

        if not clean_done:
            blockers.append(
                "stage_not_clean_done:"
                f"{task_id}:queue={queue_status}:"
                f"receipt={observed_receipt_status or receipt_error or 'unknown'}"
            )

    passed = not blockers
    receipt = {
        "schema_version": 1,
        "protocol": "BEM-949",
        "task_id": P7,
        "receipt_id": "BEM949_p7_external_release_audit",
        "created_at": now(),
        "trace_id": args.trace_id,
        "evidence_kind": "independent_runtime_audit",
        "runtime_execution_claim": True,
        "execution": {
            "runner_path": "governance/runners/bem949_release_audit_runner.py",
            "runner_sha": sha256_content(Path(__file__).resolve()),
            "runner_sha_type": "sha256_content",
            "queue_sha": sha256_content(queue_path),
            "queue_sha_type": "sha256_content",
        },
        "checks": checks,
        "blockers": blockers,
        "operator_skip_acknowledged": operator_skip_acknowledged,
        "acceptance": {
            "all_p05_to_p6_clean_done": passed,
            "limitations_absent": passed,
            "broad_release_pass_claimed": passed,
        },
        "status": "PASS" if passed else "BLOCKED",
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )

    by_id[P7].update(
        status="DONE" if passed else "BLOCKED",
        completed_at=now(),
        receipt_sha=sha256_content(out_path),
        receipt_sha_type="sha256_content",
    )
    queue.update(
        current_task=None,
        queue_state="COMPLETE" if passed else "BLOCKED",
        system_status=(
            "BEM949_RELEASE_AUDIT_PASS"
            if passed
            else "BEM949_RELEASE_AUDIT_BLOCKED"
        ),
        release_status="PASS" if passed else "VERIFIED_WITH_LIMITATIONS",
        next_action=(
            "Roadmap complete."
            if passed
            else "Resume only recorded blockers; do not claim broad Release PASS."
        ),
        updated_at=now(),
    )
    progress = queue.get("progress")
    if isinstance(progress, dict):
        completed = sum(
            1
            for task in tasks
            if isinstance(task, dict)
            and str(task.get("status", "")).startswith("DONE")
        )
        progress["tasks_done"] = completed
        total = progress.get("tasks_total")
        if isinstance(total, int) and total:
            progress["percent"] = round(completed * 100 / total, 2)

    queue_path.write_text(
        json.dumps(queue, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
