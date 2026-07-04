#!/usr/bin/env python3
import argparse,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
T="BEM949-DSM-1";W="dsm1-lifecycle-probe.yml";R=Path(__file__).resolve().parents[2];O=R/"governance/proofs/BEM949_dsm1_runtime_execution_receipt.json";Q=R/"governance/roadmap/ACTIVE_QUEUE.json"
now=lambda:datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+"\n")
p=argparse.ArgumentParser()
for k in("task-id","trace-id","workflow-id","result"):p.add_argument("--"+k,required=True)
a=p.parse_args()
if a.task_id!=T or a.workflow_id!=W:raise SystemExit("invalid_identity")
x=json.loads(Path(a.result).read_text()) if Path(a.result).exists() else {"status":"BLOCKED","task_id":T,"trace_id":a.trace_id,"result":{"blocker":"lifecycle_result_missing"}}
if not isinstance(x,dict) or x.get("task_id")!=T or x.get("trace_id")!=a.trace_id:raise SystemExit("lifecycle_identity_mismatch")
d=x.get("result") if isinstance(x.get("result"),dict) else {};ok=x.get("status")=="STATE_COMMITTED" and d.get("terminal_state")=="COMPLETED" and d.get("conclusion")=="success"
r={"task_id":T,"trace_id":a.trace_id,"status":"PASS" if ok else "BLOCKED","runtime_execution_claim":ok,"target_workflow":W,"lifecycle_result":d,"blockers":[] if ok else [str(d.get("blocker","lifecycle_not_completed"))]};save(O,r)
if not ok:print(json.dumps(r));raise SystemExit(1)
q=json.loads(Q.read_text());t=next((z for z in q["tasks"] if z.get("id")==T),None)
if not isinstance(t,dict):raise SystemExit("dsm1_queue_task_missing")
t.update({"status":"DONE","receipt":str(O.relative_to(R)),"receipt_sha":hashlib.sha256(O.read_bytes()).hexdigest(),"receipt_sha_type":"sha256_content","completed_at":now(),"trace_id":a.trace_id});q.update({"current_task":None,"queue_state":"READY","updated_at":now(),"version":int(q.get("version",0))+1});save(Q,q);print(json.dumps(r))
