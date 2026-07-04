#!/usr/bin/env python3
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
R=Path(__file__).resolve().parents[2]
Q=R/"governance/roadmap/ACTIVE_QUEUE.json"
P=R/"governance/proofs/BEM949_dsm1_runtime_execution_receipt.json"
T="BEM949-DSM-1"; W="dsm1-lifecycle-probe.yml"
E={"PENDING","AWAITING_GENUINE_RECEIPT","EVIDENCE_MISMATCH"}; M=3
def now(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def read(p):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
def stop(reason,changed=False):
    return {"action":"stop","reason":reason,"task_id":T,"queue_changed":changed}
def main(force):
    q=read(Q); ts=q.get("tasks")
    if not isinstance(ts,list): raise ValueError("queue_tasks_invalid")
    if force and force!=T: raise ValueError("dsm1_autopilot_accepts_only_BEM949_DSM_1")
    t=next((x for x in ts if isinstance(x,dict) and x.get("id")==T),None)
    if not isinstance(t,dict): raise ValueError("dsm1_task_missing")
    by={x.get("id"):x for x in ts if isinstance(x,dict)}
    cur=q.get("current_task")
    if cur and cur!=T and str(by.get(cur,{}).get("status","")).upper()=="IN_PROGRESS": return stop("different_task_in_progress")
    s=str(t.get("status","")).upper(); n=int(t.get("attempt_count",0) or 0)
    if s=="IN_PROGRESS":
        r=read(P); tr=str(t.get("trace_id","") or "")
        matched=r.get("task_id")==T and r.get("trace_id")==tr and r.get("status")=="BLOCKED" and r.get("runtime_execution_claim") is False
        if not matched: return stop("dsm1_observation_pending")
        n=max(n,1)
        if n>=M:
            z=now(); t.update({"status":"BLOCKED_OPERATOR_DECISION","blocked_at":z,"blocked_by":"DSM1_RUNTIME_ATTEMPT_LIMIT","blocker":"three_genuine_lifecycle_attempts_without_terminal_success","attempt_count":n})
            q.update({"current_task":None,"queue_state":"BLOCKED","updated_at":z})
            Q.write_text(json.dumps(q,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); return stop("dsm1_attempt_limit_reached",True)
    elif s not in E: return stop("dsm1_not_eligible")
    z=now(); tr="autopilot_bem949_dsm1_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    t.update({"status":"IN_PROGRESS","started_at":z,"trace_id":tr,"dispatch_intent":"GENUINE_GITHUB_ACTIONS_LIFECYCLE_PROBE","attempt_count":n+1})
    q.update({"current_task":T,"queue_state":"ACTIVE","updated_at":z})
    Q.write_text(json.dumps(q,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return {"action":"dispatch","task_id":T,"trace_id":tr,"workflow_id":W,"inputs":{"trace_id":tr,"task_id":T},"attempt_count":n+1,"queue_changed":True}
p=argparse.ArgumentParser(); p.add_argument("--force-task-id",default=""); p.add_argument("--output",required=True)
a=p.parse_args(); o=main(a.force_task_id.strip()); Path(a.output).write_text(json.dumps(o,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps(o,ensure_ascii=False,sort_keys=True))
