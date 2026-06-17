#!/usr/bin/env python3
"""BEM-934 request-driven repository actions."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REQUEST = ROOT / "governance/runtime/bem934_state_request.json"
PROOFS = ROOT / "governance/proofs"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run_command(args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        args,
        cwd=ROOT,
        env=merged,
        text=True,
        capture_output=True,
        check=False,
    )


def source_sha() -> str:
    result = run_command(["git", "rev-parse", "HEAD"])
    return result.stdout.strip() if result.returncode == 0 else ""


def auditor_handle_pre_regression() -> int:
    compile_result = run_command(
        [
            "python3",
            "-m",
            "py_compile",
            "governance/runners/bem931_runner_lib.py",
            "governance/runners/auditor_stage_runner.py",
            "governance/tests/test_auditor_handle_pre.py",
        ]
    )
    integration_result = run_command(
        ["python3", "governance/tests/test_auditor_handle_pre.py"],
        env={"PYTHONPATH": "governance/runners"},
    )

    integration: dict[str, Any] = {}
    if integration_result.stdout.strip():
        try:
            parsed = json.loads(integration_result.stdout)
            if isinstance(parsed, dict):
                integration = parsed
        except json.JSONDecodeError:
            integration = {"parse_error": "integration stdout was not JSON"}

    auditor_path = ROOT / "governance/runners/auditor_stage_runner.py"
    source = auditor_path.read_text(encoding="utf-8")
    checks = {
        "python_compile_pass": compile_result.returncode == 0,
        "auditor_handle_pre_channel_path_exit_zero": integration_result.returncode == 0,
        "auditor_handle_pre_channel_path_pass": integration.get("status") == "PASS",
        "accepted_variable_defined": 'accepted = verdict["status"] == "PASS"' in source,
        "misspelled_acepted_absent": "acepted =" not in source,
        "real_executor_route_verified": bool(
            integration.get("checks", {}).get("executor_route_selected")
        ),
        "real_pre_channel_consumed": bool(
            integration.get("checks", {}).get("main_consumed_real_pre_channel")
        ),
    }
    status = "PASS" if all(checks.values()) else "BLOCKED"
    receipt = {
        "status": status,
        "protocol": "BEM-934",
        "task_id": "BEM934-AUDITOR-HANDLE-PRE-REGRESSION",
        "created_at": utc_now(),
        "source_sha": source_sha(),
        "checks": checks,
        "integration": integration,
        "commands": {
            "compile_returncode": compile_result.returncode,
            "compile_stderr_tail": compile_result.stderr[-2000:],
            "integration_returncode": integration_result.returncode,
            "integration_stderr_tail": integration_result.stderr[-2000:],
        },
        "artifacts": [
            "governance/runners/auditor_stage_runner.py",
            "governance/tests/test_auditor_handle_pre.py",
        ],
        "missing": [key for key, value in checks.items() if not value],
    }
    write_json(
        PROOFS / "BEM934_auditor_handle_pre_regression_receipt.json",
        receipt,
    )
    return 0 if status == "PASS" else 1


ACTIONS = {
    "auditor_handle_pre_regression": auditor_handle_pre_regression,
}


def main() -> int:
    request = json.loads(REQUEST.read_text(encoding="utf-8"))
    action = str(request.get("action") or "").strip()
    handler = ACTIONS.get(action)
    if handler is None:
        write_json(
            PROOFS / "BEM934_state_action_blocked_receipt.json",
            {
                "status": "BLOCKED",
                "protocol": "BEM-934",
                "created_at": utc_now(),
                "action": action,
                "blocker": "unsupported_action",
            },
        )
        return 1
    return handler()


if __name__ == "__main__":
    raise SystemExit(main())
