#!/usr/bin/env python3
"""DIR.CURATOR runner: gd_to_dir -> dir_to_wrk."""
import sys
from uuid import uuid4
from bem931_runner_lib import CHANNELS, now_iso, first_pending, append_jsonl, write_result

ROLE_NAME = "DIR.CURATOR"
INBOX = CHANNELS / "gd_to_dir.jsonl"
WRK_INBOX = CHANNELS / "dir_to_wrk.jsonl"

def main() -> str:
    task = first_pending(INBOX)
    if not task:
        write_result("dir_curator_no_task", {"role": ROLE_NAME, "result": "no_task"})
        return "no_task"
    routed = {
        "trace_id": task.get("trace_id") or f"dir_{uuid4().hex[:12]}",
        "status": "pending",
        "from": ROLE_NAME,
        "to": "WRK.CURATOR",
        "task": task.get("task") or task.get("text") or "",
        "selected_object": "WRK",
        "created_at": now_iso(),
        "received_at": task.get("created_at"),
    }
    append_jsonl(WRK_INBOX, routed)
    write_result("dir_curator_routed", {**routed, "status": "completed", "next_channel": str(WRK_INBOX)})
    return "routed_to_wrk"

if __name__ == "__main__":
    print(f"RUNNER: {main()}")
    sys.exit(0)
