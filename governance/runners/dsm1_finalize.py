#!/usr/bin/env python3
"""DSM-1-only lifecycle finalizer."""
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path

T="BEM949-DSM-1"; W="dsm1-lifecycle-probe.yml"
R=Path(__file__).resolve().parents[2]
O=R/"governance/proofs/BEM949_dsm1_runtime_execution_receipt.json"
Q=R/"governance/roadmap/ACTIVE_QUEUE.json"

def ts(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def put(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def main():
 p=argparse.ArgumentParser()
 for x in ("task-id","trace-id","workflow-id","result"): p.add_argument("--"+x,required=True)
 a=p.parse_args()
 if a.task_id!=T: raise SystemExit("task_id_must_be_BEM949-DSM-1")
 if a.workflow_id!=W: raise SystemExit("workflow_id_must_be_dsm1-lifecycle-probe.yml")
 rp=Path(a.result)
 r=json.loads(rp.read_text()) if rp.exists() else {"status":"BLOCKED","task_id":T,"trace_id":a.trace_id,"result":{"blocker":"lifecycle_result_missing"}}
 if r.get("task_id") not in (None,T): raise SystemExit("lifecycle_result_task_id_mismatch")
 if r.get("trace_id") not in (None,a.trace_id): raise SystemExit("lifecycle_result_trace_id_mismatch")
 d=r.get("result",{})
 ok=r.get("status")=="STATE_COMMITTED" and d.get("terminal_state")=="COMPLETED" and d.get("conclusion")=="success"
 z={"schema_version":1,"protocol":"BEM-949","task_id":T,"created_at":ts(),"trace_id":a.trace_id,"status":"PASS" if ok else "BLOCKED","runtime_execution_claim":ok,"evidence_kind":"github_actions_api_lifecycle_poll","executor_path":"governance/runners/dispatch_executor.py","autopilot_path":".github/workflows/roadmap-autopilot.yml","target_workflow":W,"lifecycle_result":d,"acceptance":{"http_204_not_treated_as_completion":True,"dispatched_to_start_confirmed_to_terminal_observed":ok,"state_committed_recorded":ok,"task_identity_bound":True,"workflow_identity_bound":True,"trace_identity_bound":True},"blockers":[] if ok else [str(d.get("blocker","lifecycle_not_completed"))]}
 put(O,z)
 if not ok: print(json.dumps(z,ensure_ascii=False,indent=2));raise SystemExit(1)
 b=Q.read_bytes();q=json.loads(b);t=next((x for x in q.get("tasks",[]) if x.get("id")==T),None)
 if not isinstance(t,dict): raise SystemExit("dsm1_queue_task_missing")
 t.update({"status":"DONE","receipt":str(O.relative_to(R)),"receipt_sha":hashlib.sha256(O.read_bytes()).hexdigest(),"receipt_sha_type":"sha256_content","completed_at":ts(),"trace_id":a.trace_id})
 q["current_task"]=None;q["updated_at"]=ts();q["version"]=int(q.get("version",0))+1
 g=q.get("progress",{})
 if isinstance(g,dict):
  g["tasks_done"]=int(g.get("skasks_total",0))>0"
  if int(g.get("tasks_total",0)): g["percent"]=round(g["tasks_done"]/g["tasks_total"]*100,1)
 put(Q,q);print(json.dumps(z,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
