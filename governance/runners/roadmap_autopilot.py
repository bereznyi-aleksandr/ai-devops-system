#!/usr/bin/env python3
"""DSM-1-only selector; dispatch acknowledgement is not completion."""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
QUEUE=ROOT/"governance/roadmap/ACTIVE_QUEUE.json"
RECEIPT=ROOT/"governance/proofs/BEM949_dsm1_runtime_execution_receipt.json"
TASK="BEM949-DSM-1"; WORKFLOW="dsm1-lifecycle-probe.yml"
ELIGIBLE={"PENDING","AWAITING_GENUINE_RECEIPT","EVIDENCE_MISMATCH"}; LIMIT=3

def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def load(p):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def find(q):
    for x in q.get("tasks",[]):
        if isinstance(x,dict) and x.get("id")==TASK:return x
    raise ValueError("dsm1_task_missing")
def emit(action,**x):
    return {"action":action,"task_id":TASK,**x}
def persist(q):
    q["version"]=int(q.get("version",0) or 0)+1;q["updated_at"]=now();save(QUEUE,q)
def blocked_receipt(task):
    r=load(RECEIPT)
    return r.get("task_id")==TASK and r.get("trace_id")==task.get("trace_id") and r.get("status")=="BLOCKED" and r.get("runtime_execution_claim") is False
def main():
    p=argparse.ArgumentParser();p.add_argument("--force-task-id",default="");p.add_argument("--output",required=True);a=p.parse_args()
    if a.force_task_id and a.force_task_id!=TASK:raise ValueError("dsm1_only")
    q=load(QUEUE);t=find(q);status=str(t.get("status","")).upper();attempts=int(t.get("genuine_lifecycle_attempt_count",0) or 0)
    if status=="IN_PROGRESS":
        stamp=now();seen=blocked_receipt(t)
        t["stale_selection"]={"trace_id":str(t.get("trace_id") or ""),"rearmed_at":stamp,"reason":"trace_bound_terminal_blocked_receipt_seen" if seen else "no_trace_bound_terminal_receipt"}
        if seen and attempts>=LIMIT:
            t.update({"status":"BLOCKED_OPERATOR_DECISION","blocked_at":stamp,"blocker":"three_genuine_lifecycle_attempts_without_terminal_success"});q.update({"current_task":None,"queue_state":"BLOCKED"});persist(q);r=emit("stop",queue_changed=True,reason="genuine_attempt_limit_reached")
        else:
            t["status"]="AWAITING_GENUINE_RECEIPT";q.update({"current_task":None,"queue_state":"READY"});persist(q);r=emit("rearm",queue_changed=True,reason="terminal_blocked_receipt_rearmed" if seen else "stale_selection_rearmed")
    elif status not in ELIGIBLE:r=emit("stop",queue_changed=False,reason="dsm1_not_eligible",observed_status=status)
    elif attempts>=LIMIT:
        t.update({"status":"BLOCKED_OPERATOR_DECISION","blocked_at":now(),"blocker":"three_genuine_lifecycle_attempts_without_terminal_success"});q.update({"current_task":None,"queue_state":"BLOCKED"});persist(q);r=emit("stop",queue_changed=True,reason="genuine_attempt_limit_reached")
    else:
        stamp=now();trace="autopilot_bem949_dsm1_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        t.update({"status":"IN_PROGRESS","started_at":stamp,"trace_id":trace,"dispatch_intent":"GENUINE_GITHUB_ACTIONS_LIFECYCLE_PROBE","genuine_lifecycle_attempt_count":attempts+1});q.update({"current_task":TASK,"queue_state":"ACTIVE"});persist(q)
        r=emit("dispatch",workflow_id=WORKFLOW,trace_id=trace,inputs={"trace_id":trace,"task_id":TASK},genuine_lifecycle_attempt_count=attempts+1,queue_changed=True)
    save(Path(a.output),r);print(json.dumps(r,ensure_ascii=False,sort_keys=True))
if __name__=="__main__":main()
