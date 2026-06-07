#!/usr/bin/env python3
"""WRK-Cx.EXECUTOR runner: executes minimal task and sends result to auditor."""
import json
import os
import sys
from uuid import uuid4
from bem931_runner_lib import ROOT, CHANNELS, now_iso, first_pending, append_jsonl, write_result

CONTOURS = ["WRK-C1", "WRK-C2", "WRK-C3"]

def channel_name(contour_id: str, suffix: str):
    return CHANNELS / f"{contour_id.lower().replace('-', '_')}_to_{suffix}.jsonl"

def find_task():
    for contour in CONTOURS:
        path = channel_name(contour, "executor")
        task = first_pending(path)
        if task:
            return contour, task
    return None, None

def main() -> str:
    contour_id, task = find_task()
    if not task:
        write_result("executor_no_task", {"role": "WRK-Cx.EXECUTOR", "result": "no_task"})
        return "no_task"
    role_name = f"{contour_id}.EXECUTOR"
    trace_id = task.get("trace_id") or f"exec_{uuid4().hex[:12]}"
    work_dir = ROOT / "governance" / "results" / trace_id
    work_dir.mkdir(parents=True, exist_ok=True)
    result_path = work_dir / "worker_result.json"
    result = {
        "trace_id": trace_id, "role": role_name, "contour_id": contour_id,
        "task": task.get("task") or "", "plan_path": task.get("plan_path"),
        "commit_sha": os.environ.get("GITHUB_SHA", "local-no-sha"),
        "result": "executed_minimal_task", "created_at": now_iso(),
    }
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    outbox = channel_name(contour_id, "auditor_post")
    routed = {
        "trace_id": trace_id, "status": "pending", "from": role_name, "to": f"{contour_id}.AUDITOR",
        "contour_id": contour_id, "phase": "post_check", "result_path": str(result_path.relative_to(ROOT)),
        "task": task.get("task") or "", "created_at": now_iso(),
    }
    append_jsonl(outbox, routed)
    write_result("executor_completed", {"**": "", **routed, "status": "completed"})
    return f"{contour_id}_result_sent_to_auditor"

if __name__ == "__main__":
    print(f"RUNNER: {main()}")
    sys.exit(0)
