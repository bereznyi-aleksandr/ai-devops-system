#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

ROOT = Path(__file__).resolve().parents[2]
HEALTH = ROOT / "governance" / "scripts" / "system_health_check_v1.py"
STATUS = ROOT / "governance" / "scripts" / "system_status_v1.py"
ROUTER = ROOT / "governance" / "scripts" / "system_router_v1.py"
PACKETS = ROOT / "governance" / "runtime" / "packets"


class DoctorError(RuntimeError):
    pass


def run_json_script(path: Path) -> Tuple[int, Dict[str, Any], str]:
    proc = subprocess.run(
        [sys.executable, str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    raw = proc.stdout.strip() or proc.stderr.strip()
    if not raw:
        payload = {}
    else:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as e:
            raise DoctorError(f"{path.relative_to(ROOT)} did not return valid JSON: {e}") from e
    return proc.returncode, payload, raw


def select_packet_path(next_role: str) -> str:
    if next_role == "EXECUTOR":
        return str((PACKETS / "executor_packet_current.json").relative_to(ROOT))
    if next_role == "AUDITOR":
        return str((PACKETS / "auditor_packet_current.json").relative_to(ROOT))
    return ""


def packet_summary(packet_path: str) -> Dict[str, str]:
    if not packet_path:
        return {"path": "", "role": "", "task_id": "", "input_event_id": "", "next_action": ""}
    path = ROOT / packet_path
    if not path.exists():
        return {"path": packet_path, "role": "", "task_id": "", "input_event_id": "", "next_action": "", "missing": "true"}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "path": packet_path,
        "role": data.get("role", ""),
        "task_id": data.get("task_id", ""),
        "input_event_id": data.get("input_event_id", ""),
        "next_action": data.get("next_action", ""),
        "current_state": data.get("current_state", ""),
    }


def main() -> int:
    try:
        h_code, health, _ = run_json_script(HEALTH)
        s_code, status, _ = run_json_script(STATUS)
        r_code, router, _ = run_json_script(ROUTER)

        issues = []
        notes = []

        health_result = health.get("result", "")
        status_result = status.get("result", "")

        if health_result == "BLOCKED" or h_code == 1:
            issues.append("Health check is blocked")
        elif health_result == "ATTENTION" or h_code == 2:
            issues.append("Health check reported attention-level issues")

        if status_result != "SUCCESS":
            issues.append("Status view did not return SUCCESS")

        current_task = status.get("current_task_id", "")
        current_state = status.get("current_state", "")
        last_event_id = status.get("last_event_id", "")
        next_role = status.get("next_role", "")
        next_action = status.get("next_action", "")
        latest_artifact_ref = status.get("latest_artifact_ref", "")

        if r_code != 0:
            issues.append("Router failed to read current ledger tail")
            packet = {"path": "", "role": "", "task_id": "", "input_event_id": "", "next_action": ""}
        else:
            packet = packet_summary(select_packet_path(router.get("next_role", "")))
            if router.get("current_task_id", "") != current_task:
                issues.append("Router current_task_id disagrees with status view")
            if router.get("current_state", "") != current_state:
                issues.append("Router current_state disagrees with status view")
            if router.get("current_event_id", "") != last_event_id:
                issues.append("Router current_event_id disagrees with status last_event_id")
            if router.get("next_role", "") != next_role:
                issues.append("Router next_role disagrees with status next_role")
            if router.get("next_action", "") != next_action:
                issues.append("Router next_action disagrees with status next_action")

        if packet.get("missing") == "true":
            issues.append(f"Expected current packet is missing: {packet.get('path','')}")
        else:
            if packet.get("role", "") and packet.get("role", "") != next_role:
                issues.append("Current packet role disagrees with status next_role")
            if packet.get("task_id", "") and packet.get("task_id", "") != current_task:
                issues.append("Current packet task_id disagrees with status current_task_id")
            if packet.get("input_event_id", "") and packet.get("input_event_id", "") != last_event_id:
                issues.append("Current packet input_event_id disagrees with status last_event_id")
            if packet.get("next_action", "") and packet.get("next_action", "") != next_action:
                issues.append("Current packet next_action disagrees with status next_action")

        latest_result = status.get("latest_result_manifest", {}) or {}
        if latest_result:
            if latest_result.get("task_id", "") and latest_result.get("task_id", "") != current_task:
                issues.append("Latest result manifest task_id disagrees with current_task_id")
            notes.append(
                f"Latest result manifest: {latest_result.get('path','')} ({latest_result.get('role','')} / {latest_result.get('result','')})"
            )

        if latest_artifact_ref:
            notes.append(f"Latest artifact ref: {latest_artifact_ref}")
        notes.append(f"Current route: {next_role} / {next_action}")
        notes.append(f"Current state: {current_state}")

        if any("blocked" in x.lower() or "missing" in x.lower() for x in issues):
            verdict = "BROKEN"
        elif issues:
            verdict = "ATTENTION"
        else:
            verdict = "HEALTHY"

        next_step = ""
        if verdict == "HEALTHY":
            if next_role and next_action:
                next_step = f"Run system_orchestrator_v1.py, then execute the suggested {next_role} / {next_action} step."
            else:
                next_step = "Inspect ledger tail and protocol; next route is empty."
        elif verdict == "ATTENTION":
            next_step = "Review issues, then rerun system_health_check_v1.py and system_status_v1.py."
        else:
            next_step = "Fix the blocking mismatch or missing file before running the next role."

        report = {
            "system_doctor_version": "v1",
            "verdict": verdict,
            "current_task_id": current_task,
            "current_state": current_state,
            "last_event_id": last_event_id,
            "next_role": next_role,
            "next_action": next_action,
            "current_packet": packet,
            "latest_result_manifest": latest_result,
            "issues": issues,
            "notes": notes,
            "recommended_next_step": next_step,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if verdict == "HEALTHY" else 2 if verdict == "ATTENTION" else 1
    except Exception as e:
        print(json.dumps({
            "system_doctor_version": "v1",
            "verdict": "BROKEN",
            "error": str(e),
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
