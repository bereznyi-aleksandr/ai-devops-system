#!/usr/bin/env python3
"""WRK-Cx.AUDITOR runner: pre-checks plan, post-checks executor result."""
import sys
from uuid import uuid4
from bem931_runner_lib import ROOT, CHANNELS, now_iso, first_pending, append_jsonl, write_result

CONTOURS = ["WRK-C1", "WRK-C2", "WRK-C3"]
CURATOR_FEEDBACK = CHANNELS / "wrk_to_curator_feedback.jsonl"


def channel_name(contour_id: str, suffix: str):
    return CHANNELS / f"{contour_id.lower().replace('-', '_')}_to_{suffix}.jsonl"


def find_task(suffix: str):
    for contour in CONTOURS:
        path = channel_name(contour, suffix)
        task = first_pending(path)
        if task:
            return contour, task
    return None, None


def handle_pre(contour_id: str, task: dict) -> str:
    role_name = f"{contour_id}.AUDITOR"
    plan_path = ROOT / task.get("plan_path", "")
    ok = plan_path.exists() and plan_path.stat().st_size > 50
    outbox = channel_name(contour_id, "executor")
    routed = {
        "trace_id": task.get("trace_id") or f"audit_pre_{uuid4().hex[:12]}",
        "status": "pending" if ok else "rejected",
        "from": role_name,
        "to": f"{contour_id}.EXECUTOR",
        "contour_id": contour_id,
        "phase": "execute",
        "pre_check": "PASS" if ok else "FAIL",
        "plan_path": task.get("plan_path"),
        "task": task.get("task") or "",
        "created_at": now_iso(),
    }
    if ok:
        append_jsonl(outbox, routed)
    write_result("auditor_pre_check", {**routed, "status": "completed", "next_channel": str(outbox)})
    return f"{contour_id}_pre_check_{'pass' if ok else 'fail'}"


def handle_post(contour_id: str, task: dict) -> str:
    role_name = f"{contour_id}.AUDITOR"
    result_path = ROOT / task.get("result_path", "")
    ok = result_path.exists() and result_path.stat().st_size > 50
    feedback = {
        "trace_id": task.get("trace_id") or f"audit_post_{uuid4().hex[:12]}",
        "status": "completed",
        "from": role_name,
        "to": "WRK.CURATOR",
        "contour_id": contour_id,
        "phase": "post_check",
        "acceptance": "PASS" if ok else "FAIL",
        "result_path": task.get("result_path"),
        "created_at": now_iso(),
    }
    append_jsonl(CURATOR_FEEDBACK, feedback)
    write_result("auditor_post_check", feedback)
    return f"{contour_id}_post_check_{'pass' if ok else 'fail'}"


def main() -> str:
    contour_id, post = find_task("auditor_post")
    if post:
        return handle_post(contour_id, post)
    contour_id, pre = find_task("auditor_pre")
    if pre:
        return handle_pre(contour_id, pre)
    write_result("auditor_no_task", {"role": "WRK-Cx.AUDITOR", "result": "no_task"})
    return "no_task"


if __name__ == "__main__":
    print(f"RUNNER: {main()}")
    sys.exit(0)
