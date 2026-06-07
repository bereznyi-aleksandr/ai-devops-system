#!/usr/bin/env python3
"""WRK-Cx.ANALYST runner: creates plan and sends it to auditor pre-check."""
import json
import sys
from uuid import uuid4
from bem931_runner_lib import ROOT, CHANNELS, ARTIFACTS, now_iso, first_pending, append_jsonl, write_result

CONTOURS = ["WRK-C1", "WRK-C2", "WRK-C3"]

def channel_name(contour_id: str, suffix: str):
    return CHANNELS / f"{contour_id.lower().replace('-', '_')}_to_{suffix}.jsonl"

def find_task():
    for contour in CONTOURS:
        path = channel_name(contour, "analyst")
        task = first_pending(path)
        if task:
            return contour, task
    return None, None

def main() -> str:
    contour_id, task = find_task()
    if not task:
        write_result("analyst_no_task", {"role": "WRK-Cx.ANALYST", "result": "no_task"})
        return "no_task"
    role_name = f"{contour_id}.ANALYST"
    trace_id = task.get("trace_id") or f"analysis_{uuid4().hex[:12]}"
    plan_dir = ARTIFACTS / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plan_dir / f"{trace_id}_plan.json"
    plan = {
        "trace_id": trace_id,
        "role": role_name,
        "contour_id": contour_id,
        "task": task.get("task") or "",
        "steps": ["verify objective", "prepare execution boundary", "request auditor pre-check"],
        "created_at": now_iso(),
    }
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    outbox = channel_name(contour_id, "auditor_pre")
    routed = {
        "trace_id": trace_id, "status": "pending", "from": role_name, "to": f"{contour_id}.AUDITOR",
        "contour_id": contour_id, "phase": "pre_check", "plan_path": str(plan_path.relative_to(ROOT)),
        "task": task.get("task") or "", "created_at": now_iso(),
    }
    append_jsonl(outbox, routed)
    write_result("analyst_plan", {**routed, "status": "completed", "next_channel": str(outbox)})
    return f"{contour_id}_plan_sent_to_auditor"

if __name__ == "__main__":
    print(f"RUNNER: {main()}")
    sys.exit(0)
