#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTER = ROOT / "governance" / "scripts" / "system_router_v1.py"
PACKET_WRITER = ROOT / "governance" / "scripts" / "system_packet_writer_v1.py"
ROLE_LAUNCHER = ROOT / "governance" / "scripts" / "system_role_launcher_v2.py"
RESULT_INTAKE = ROOT / "governance" / "scripts" / "system_result_intake_v1.py"
LEDGER_WRITER = ROOT / "governance" / "scripts" / "system_ledger_writer_v1.py"


class OrchestratorError(RuntimeError):
    pass


def run_json_script(path: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        raise OrchestratorError(
            f"{path.relative_to(ROOT)} failed: {proc.stderr.strip() or proc.stdout.strip() or proc.returncode}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise OrchestratorError(f"{path.relative_to(ROOT)} did not return valid JSON: {e}") from e


def main() -> int:
    try:
        router = run_json_script(ROUTER)
        packet_writer = run_json_script(PACKET_WRITER)
        role_launcher = run_json_script(ROLE_LAUNCHER)

        report = {
            "system_orchestrator_version": "v1",
            "result": "READY_FOR_ROLE_EXECUTION",
            "phase": "PRE_ROLE_EXECUTION",
            "current_event_id": router.get("current_event_id", ""),
            "current_task_id": router.get("current_task_id", ""),
            "current_state": router.get("current_state", ""),
            "next_role": router.get("next_role", ""),
            "next_action": router.get("next_action", ""),
            "written_packet_path": packet_writer.get("written_packet_path", ""),
            "runner_command": role_launcher.get("runner_command", ""),
            "instruction": "Run runner_command in the current interactive terminal. After the role completes, run: python3 governance/scripts/system_orchestrator_v1.py --post",
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({
            "system_orchestrator_version": "v1",
            "result": "BLOCKED",
            "phase": "PRE_ROLE_EXECUTION",
            "error": str(e),
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--post":
        try:
            intake = run_json_script(RESULT_INTAKE)
            ledger_writer = run_json_script(LEDGER_WRITER)
            report = {
                "system_orchestrator_version": "v1",
                "result": "SUCCESS",
                "phase": "POST_ROLE_EXECUTION",
                "latest_result_manifest": intake.get("latest_result_manifest", ""),
                "result_role": intake.get("result_role", ""),
                "result_value": intake.get("result_value", ""),
                "written_event_id": ledger_writer.get("written_event_id", ""),
                "written_task_id": ledger_writer.get("written_task_id", ""),
                "written_status": ledger_writer.get("written_status", ""),
                "written_next_role": ledger_writer.get("written_next_role", ""),
                "written_next_action": ledger_writer.get("written_next_action", ""),
            }
            print(json.dumps(report, ensure_ascii=False, indent=2))
            raise SystemExit(0)
        except Exception as e:
            print(json.dumps({
                "system_orchestrator_version": "v1",
                "result": "BLOCKED",
                "phase": "POST_ROLE_EXECUTION",
                "error": str(e),
            }, ensure_ascii=False, indent=2), file=sys.stderr)
            raise SystemExit(1)

    raise SystemExit(main())
