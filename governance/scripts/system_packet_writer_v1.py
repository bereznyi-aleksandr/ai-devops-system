#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTER = ROOT / "governance" / "scripts" / "system_router_v1.py"


class PacketWriterError(RuntimeError):
    pass


def run_router() -> dict:
    proc = subprocess.run(
        [sys.executable, str(ROUTER)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        raise PacketWriterError(proc.stderr.strip() or proc.stdout.strip() or "system_router_v1 failed")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise PacketWriterError(f"Router output is not valid JSON: {e}") from e


def main() -> int:
    try:
        report = run_router()
        packet_path_rel = report["suggested_packet_path"]
        packet = report["suggested_packet"]

        packet_path = ROOT / packet_path_rel
        packet_path.parent.mkdir(parents=True, exist_ok=True)
        packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = {
            "system_packet_writer_version": "v1",
            "result": "SUCCESS",
            "written_packet_path": packet_path_rel,
            "next_role": report.get("next_role", ""),
            "next_action": report.get("next_action", ""),
            "current_event_id": report.get("current_event_id", ""),
            "current_task_id": report.get("current_task_id", ""),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({
            "system_packet_writer_version": "v1",
            "result": "BLOCKED",
            "error": str(e),
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
