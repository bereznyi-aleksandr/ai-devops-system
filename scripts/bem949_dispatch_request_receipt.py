#!/usr/bin/env python3
"""Persist a truthful receipt for a safe workflow-dispatch attempt."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--component", required=True)
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--target-workflow", required=True)
    parser.add_argument("--allow-dispatch", choices=("true", "false"), required=True)
    parser.add_argument("--dispatch-exit-code", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    allowed = args.allow_dispatch == "true"
    dispatched = allowed and args.dispatch_exit_code == 0
    status = "DISPATCHED" if dispatched else "BLOCKED"
    blockers = []
    if not allowed:
        blockers.append("safe_dispatch_gate_not_enabled")
    elif args.dispatch_exit_code != 0:
        blockers.append("workflow_dispatch_command_failed")
    payload = {
        "schema_version": 1,
        "protocol": "BEM-949",
        "task_id": "BEM949-P2-FUNCTIONAL-RESTORE",
        "component": args.component,
        "trace_id": args.trace_id,
        "created_at": now(),
        "status": status,
        "target_workflow": args.target_workflow,
        "target_workflow_type": "workflow_id",
        "safe_dispatch_gate_enabled": allowed,
        "dispatch_attempted": allowed,
        "dispatch_exit_code": args.dispatch_exit_code,
        "checks": {
            "safe_gate_checked": True,
            "dispatch_command_result_recorded": True,
            "http_or_cli_dispatch_not_relabelled_as_completion": True,
        },
        "blockers": blockers,
        "non_claim": "DISPATCHED records only a dispatch command outcome. A separate terminal provider report is required for execution success.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
