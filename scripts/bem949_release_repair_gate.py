#!/usr/bin/env python3
"""Evaluate release readiness through a safe, non-mutating BEM-949 gate."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "governance/roadmap/ACTIVE_QUEUE.json"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-release", choices=("true", "false"), default="false")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    current = queue.get("current_task")
    queue_state = queue.get("queue_state")
    release_status = queue.get("release_status")
    broad_pass = (
        queue_state == "COMPLETE"
        and current is None
        and release_status == "PASS"
        and queue.get("protocol") == "BEM-949"
    )
    allowed = args.allow_release == "true"
    status = "PASS" if broad_pass and allowed else "BLOCKED"
    blockers = []
    if not allowed:
        blockers.append("operator_safe_gate_not_enabled")
    if queue.get("protocol") != "BEM-949":
        blockers.append("current_protocol_is_not_bem949")
    if queue_state != "COMPLETE":
        blockers.append("roadmap_not_complete")
    if current is not None:
        blockers.append("active_task_present")
    if release_status != "PASS":
        blockers.append("release_status_is_not_broad_pass")

    payload = {
        "schema_version": 1,
        "protocol": "BEM-949",
        "task_id": "BEM949-P2-FUNCTIONAL-RESTORE",
        "component": "bem931-v36-release-repair-gate",
        "created_at": now(),
        "status": status,
        "scope": "Non-mutating release gate. It can block an unsafe release but cannot create a PASS.",
        "safe_gate_enabled": allowed,
        "queue_path": "governance/roadmap/ACTIVE_QUEUE.json",
        "queue_snapshot": {
            "protocol": queue.get("protocol"),
            "queue_state": queue_state,
            "current_task": current,
            "release_status": release_status,
        },
        "checks": {
            "queue_read": True,
            "broad_pass_preconditions_checked": True,
            "no_release_state_mutation": True,
            "pass_requires_operator_gate": True,
        },
        "blockers": blockers,
        "non_claim": "A blocked result preserves the current release status and does not repair or close any prior protocol.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
