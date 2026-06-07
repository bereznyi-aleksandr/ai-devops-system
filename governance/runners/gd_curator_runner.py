#!/usr/bin/env python3
"""GD.CURATOR runner: operator_to_gd -> gd_to_dir."""
import sys
from uuid import uuid4
from bem931_runner_lib import CHANNELS, now_iso, first_pending, append_jsonl, write_result

ROLE_NAME = "GD.CURATOR"
INBOX = CHANNELS / "operator_to_gd.jsonl"
DIR_INBOX = CHANNELS / "gd_to_dir.jsonl"

def main() -> str:
    task = first_pending(INBOX)
    if not task:
        write_result("gd_curator_no_task", {"role": ROLE_NAME, "result": "no_task"})
        return "no_task"
    routed = {
        "trace_id": task.get("trace_id") or f"gd_{uuid4().hex[:12]}",
        "status": "pending",
        "from": ROLE_NAME,
        "to": "DIR.CURATOR",
        "task": task.get("task") or task.get("text") or "",
        "received_at": task.get("created_at"),
        "created_at": now_iso(),
    }
    append_jsonl(DIR_INBOX, routed)
    write_result("gd_curator_routed", {**routed, "status": "completed", "next_channel": str(DIR_INBOX)})
    return "routed_to_dir"

if __name__ == "__main__":
    print(f"RUNNER: {main()}")
    sys.exit(0)
