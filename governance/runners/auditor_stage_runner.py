#!/usr/bin/env python3
"""WRK-C1.AUDITOR runner: pre-checks plan, post-checks executor result."""
import sys
from uuid import uuid4
from bem931_runner_lib import ROOT, CHANNELS, now_iso, first_pending, append_jsonl, write_result

ROLE_NAME = "WRK-C1.AUDITOR"
PRE_INBOX = CHANNELS / "wrk_c1_to_auditor_pre.jsonl"
POST_INBOX = CHANNELS / "wrk_c1_to_auditor_post.jsonl"
EXECUTOR_INBOX = CHANNELS / "wrk_c1_to_executor.jsonl"
CURATOR_FEEDBACK = CHANNELS / "wrk_to_curator_feedback.jsonl"

def handle_pre(task: dict) -> str:
    plan_path = ROOT / task.get("plan_path", "")
    ok = plan_path.exists() and plan_path.stat().st_size > 50
    routed = {"trace_id": task.get("trace_id") or f"audit_pre_{uuid4().hex[:12]}", "status": "pending" if ok else "rejected", "from": ROLE_NAME, "to": "WRK-C1.EXECUTOR", "phase": "execute", "pre_check": "PASS" if ok else "FAIL", "plan_path": task.get("plan_path"), "task": task.get("task") or "", "created_at": now_iso()}
    if ok:
        append_jsonl(EXECUTOR_INBOX, routed)
    write_result("auditor_pre_check", {**routed, "status": "completed"})
    return "pre_check_pass" if ok else "pre_check_fail"

def handle_post(task: dict) -> str:
    result_path = ROOT / task.get("result_path", "")
    ok = result_path.exists() and result_path.stat().st_size > 50
    feedback = {"trace_id": task.get("trace_id") or f"audit_post_{uuid4().hex[:12]}", "status": "completed", "from": ROLE_NAME, "to": "WRK.CURATOR", "phase": "post_check", "acceptance": "PASS" if ok else "FAIL", "result_path": task.get("result_path"), "created_at": now_iso()}
    append_jsonl(CURATOR_FEEDBACK, feedback)
    write_result("auditor_post_check", feedback)
    return "post_check_pass" if ok else "post_check_fail"

def main() -> str:
    post = first_pending(POST_INBOX)
    if post:
        return handle_post(post)
    pre = first_pending(PRE_INBOX)
    if pre:
        return handle_pre(pre)
    write_result("auditor_no_task", {"role": ROLE_NAME, "result": "no_task"})
    return "no_task"

if __name__ == "__main__":
    print(f"RUNNER: {main()}")
    sys.exit(0)
