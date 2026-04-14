#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WRITER = ROOT / "governance" / "scripts" / "system_packet_writer_v1.py"
EXECUTOR_RUNNER = ROOT / "governance" / "scripts" / "run_executor_codex_v2.sh"
AUDITOR_RUNNER = ROOT / "governance" / "scripts" / "run_auditor_codex_v1.sh"


class RoleLauncherError(RuntimeError):
    pass


def run_packet_writer() -> dict:
    proc = subprocess.run(
        [sys.executable, str(WRITER)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RoleLauncherError(proc.stderr.strip() or proc.stdout.strip() or "system_packet_writer_v1 failed")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RoleLauncherError(f"Packet writer output is not valid JSON: {e}") from e


def build_runner_command(next_role: str) -> str:
    if next_role == "EXECUTOR":
        runner = EXECUTOR_RUNNER
    elif next_role == "AUDITOR":
        runner = AUDITOR_RUNNER
    else:
        raise RoleLauncherError(f"Unsupported next_role: {next_role}")

    if not runner.exists():
        raise RoleLauncherError(f"Missing runner: {runner.relative_to(ROOT)}")

    return f"bash {runner.relative_to(ROOT)}"


def main() -> int:
    try:
        writer_result = run_packet_writer()
        next_role = writer_result.get("next_role", "")
        next_action = writer_result.get("next_action", "")
        runner_command = build_runner_command(next_role)

        result = {
            "system_role_launcher_version": "v2",
            "result": "READY",
            "mode": "TTY_SAFE_MANUAL_LAUNCH",
            "next_role": next_role,
            "next_action": next_action,
            "written_packet_path": writer_result.get("written_packet_path", ""),
            "current_event_id": writer_result.get("current_event_id", ""),
            "current_task_id": writer_result.get("current_task_id", ""),
            "runner_command": runner_command,
            "instruction": "Run the runner_command manually in the current interactive terminal so Codex gets a real TTY.",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({
            "system_role_launcher_version": "v2",
            "result": "BLOCKED",
            "error": str(e),
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
