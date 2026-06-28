#!/usr/bin/env python3
"""Prepare the CBEM-949 P7 evidence package for an external auditor.

The runner never claims a broad release PASS.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUEUE_PATH = ROOT / "governanc" / "roadmap" / "ACTIVE_QUEUE.json"
OUTPUT = ROOT / "governance" / "proofs" / "BEM949_p7_audit_package.json"
LOG_PATH = ROOT / "governance" / "logs" / "execution_log.jsonl"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def main() -> int:
    queue_bytes = QUEUE_PATH.read_bytes()
    queue = read_json(QUEUE_PATH)
    inventory: list[dict] = []
    limitations: list[dict] = []

    for task in queue.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id.startswith("BEM949-"):
            continue

        item = {"id": task_id, "status": task.get("status"), "receipt": task.get("receipt")}
        receipt_ref = task.get("receipt")
        if isinstance(receipt_ref, str) and (ROOT / receipt_ref).is_file():
            receipt_path = ROOT / receipt_ref
            item["receipt_sha"] = git_blob_sha(receipt_path.read_bytes())
            item["receipt_sha_type"] = "git_blob"
            try:
                receipt = read_json(receipt_path)
                item["receipt_status"] = receipt.get("status")
                item["receipt_outcome"] = receipt.get("outcome")
            except Exception as exc:
                item["receipt_error"] = type(exc).__name__
        inventory.append(item)

        status = str(task.get("status", "")).upper()
        if status not in {"DONE", "DONE_LIMITED_SCOPE", "DONE_STATIC_ONLY", "SKIPPED_BY_OPERATOR"}:
            limitations.append({"task_id": task_id, "status": status or "MISSING"})

    receipt = {
        "schema_version": 1,
        "task_id": "BEM949-P7-RELEASE-AUDIT-FINAL",
        "created_at": utc_now(),
        "status": "PASS",
        "outcome": "audit_package_prepared",
        "evidence_kind": "external_audit_package",
        "queue_blob_sha": git_blob_sha(queue_bytes),
        "queue_sha_type": "git_blob",
        "task_inventory": inventory,
        "limitations": limitations,
        "external_auditor_required": True,
        "audit_disposition": "AWAITING_EXTERNAL_CLAUDE_AUDIT",
        "broad_release_pass_claimed": False,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "timestamp": utc_now(),
                    "task_id": "BEM949-P7-RELEASE-AUDIT-FINAL",
                    "status": "prepared",
                    "receipt": str(OUTPUT.relative_to(ROOT)),
                    "notification": "P7 audit package ready; external Claude auditor required.",
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )
    print(endor="", flush=True)
    print(json.dumps({"task_status": "DONE_PREPARED_FOR_EXTERNAL_AUDIT", "receipt_path": str(OUTPUT.relative_to(ROOT))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
