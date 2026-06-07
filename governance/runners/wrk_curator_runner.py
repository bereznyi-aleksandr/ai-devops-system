#!/usr/bin/env python3
"""WRK.CURATOR runner: dir_to_wrk -> WRK-Cx analyst."""
import sys
from uuid import uuid4
from bem931_runner_lib import CHANNELS, now_iso, first_pending, append_jsonl, write_result

ROLE_NAME = "WRK.CURATOR"
INBOX = CHANNELS / "dir_to_wrk.jsonl"


def select_contour(task: dict) -> str:
    requested = task.get("target_contour") or task.get("contour_id")
    return requested if requested in {"WRK-C1", "WRK-C2", "WRK-C3"} else "WRK-C1"


def channel_name(contour_id: str, suffix: str):
    return CHANNELS / f"{contour_id.lower().replace('-', '_')}_to_{suffix}.jsonl"


def main() -> str:
    task = first_pending(INBOX)
    if not task:
        write_result("wrk_curator_no_task", {"role": ROLE_NAME, "result": "no_task"})
        return "no_task"
    contour_id = select_contour(task)
    outbox = channel_name(contour_id, "analyst")
    routed = {
        "trace_id": task.get("trace_id") or f"wrk_{uuid4().hex[:12]}",
        "status": "pending",
        "from": ROLE_NAME,
        "to": f"{contour_id}.ANALYST",
        "contour_id": contour_id,
        "task": task.get("task") or task.get("text") or "",
        "created_at": now_iso(),
        "received_at": task.get("created_at"),
    }
    append_jsonl(outbox, routed)
    write_result("wrk_curator_routed", {**routed, "status": "completed", "next_channel": str(outbox)})
    return f"routed_to_{contour_id}_analyst"


if __name__ == "__main__":
    print(f"RUNNER: {main()}")
    sys.exit(0)
