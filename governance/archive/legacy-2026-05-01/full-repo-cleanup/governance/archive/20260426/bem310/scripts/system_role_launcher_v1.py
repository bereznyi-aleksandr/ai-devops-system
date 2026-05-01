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


def launch_runner(next_role: str) -> subprocess.CompletedProcess[str]:
    if next_role == "EXECUTOR":
        runner = EXECUTOR_RUNNER
    elif next_role == "AUDITOR":
        runner = AUDITOR_RUNNER
    else:
        raise RoleLauncherError(f"Unsupported next_role: {next_role}")

    if not runner.exists():
        raise RoleLauncherError(f"Missing runner: {runner.relative_to(ROOT)}")

    return subprocess.run(
        ["bash", str(runner)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def main() -> int:
    try:
        writer_result = run_packet_writer()
        next_role = writer_result.get("next_role", "")
        next_action = writer_result.get("next_action", "")

        proc = launch_runner(next_role)

        result = {
            "system_role_launcher_version": "v1",
            "result": "SUCCESS" if proc.returncode == 0 else "PARTIAL",
            "next_role": next_role,
            "next_action": next_action,
            "written_packet_path": writer_result.get("written_packet_path", ""),
            "runner_exit_code": proc.returncode,
            "stdout_tail": proc.stdout[-4000:] if proc.stdout else "",
            "stderr_tail": proc.stderr[-4000:] if proc.stderr else "",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if proc.returncode == 0 else 2
    except Exception as e:
        print(json.dumps({
            "system_role_launcher_version": "v1",
            "result": "BLOCKED",
            "error": str(e),
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
