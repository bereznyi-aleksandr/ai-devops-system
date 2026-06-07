#!/usr/bin/env python3
"""WRK-C1.EXECUTOR runner: executes minimal task and sends result to auditor."""
import json
import os
import sys
from uuid import uuid4
from bem931_runner_lib import ROOT, CHANNELS, now_iso, first_pending, append_jsonl, write_result

ROLE_NAME = "WRK-C1.EXECUTOR"
INBOX = CHANNELS / "wrk_c1_to_executor.jsonl"
AUDITOR_POST = CHANNELS / "wrk_c1_to_auditor_post.jsonl"

def main() -> str:
    task = first_pending(INBOX)
    if not task:
        write_result("executor_no_task", {"role": ROLE_NAME, "result": "no_task"})
        return "no_task"
    trace_id = task.get("trace_id") or f"exec_{uuid4().hex[:12]}"
    work_dir = ROOT / "governance" / "results" / trace_id
    work_dir.mkdir(parents=True, exist_ok=True)
    result_path = work_dir / "worker_result.json"
    result = {"trace_id": trace_id, "role": ROLE_NAME, "task": task.get("task") or "", "plan_path": task.get("plan_path"), "commit_sha": os.environ.get("GITHUB_SHA", "local-no-sha"), "result": "executed_minimal_task", "created_at": now_iso()}
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    routed = {"trace_id": trace_id, "status": "pending", "from": ROLE_NAME, "to": "WRK-C1.AUDITOR", "phase": "post_check", "result_path": str(result_path.relative_to(ROOT)), "task": task.get("task") or "", "created_at": now_iso()}
    append_jsonl(AUDITOR_POST, routed)
    write_result("executor_completed", {**routed, "status": "completed"})
    return "result_sent_to_auditor"

if __name__ == "__main__":
    print(f"RUNNER: {main()}")
    sys.exit(0)
