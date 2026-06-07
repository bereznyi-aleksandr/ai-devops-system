#!/usr/bin/env python3
"""WRK-C1.ANALYST runner: creates plan and sends it to auditor pre-check."""
import json
import sys
from uuid import uuid4
from bem931_runner_lib import ROOT, CHANNELS, ARTIFACTS, now_iso, first_pending, append_jsonl, write_result

ROLE_NAME = "WRK-C1.ANALYST"
INBOX = CHANNELS / "wrk_c1_to_analyst.jsonl"
AUDITOR_PRE = CHANNELS / "wrk_c1_to_auditor_pre.jsonl"

def main() -> str:
    task = first_pending(INBOX)
    if not task:
        write_result("analyst_no_task", {"role": ROLE_NAME, "result": "no_task"})
        return "no_task"
    trace_id = task.get("trace_id") or f"analysis_{uuid4().hex[:12]}"
    plan_dir = ARTIFACTS / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plan_dir / f"{trace_id}_plan.json"
    plan = {"trace_id": trace_id, "role": ROLE_NAME, "contour_id": task.get("contour_id", "WRK-C1"), "task": task.get("task") or "", "steps": ["verify objective", "prepare execution boundary", "request auditor pre-check"], "created_at": now_iso()}
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    routed = {"trace_id": trace_id, "status": "pending", "from": ROLE_NAME, "to": "WRK-C1.AUDITOR", "phase": "pre_check", "plan_path": str(plan_path.relative_to(ROOT)), "task": task.get("task") or "", "created_at": now_iso()}
    append_jsonl(AUDITOR_PRE, routed)
    write_result("analyst_plan", {**routed, "status": "completed"})
    return "plan_sent_to_auditor"

if __name__ == "__main__":
    print(f"RUNNER: {main()}")
    sys.exit(0)
