#!/usr/bin/env python3
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
T="BEM949-DSM-1";W="dsm1-lifecycle-probe.yml";R=Path(__file__).resolve().parents[2];O=R/"governance/proofs/BEM949_dsm1_runtime_execution_receipt.json";Q=R/"governance/roadmap/ACTIVE_QUEUE.json"
def n():return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def put(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+"\n")
def main():
 p=argparse.ArgumentParser()
 for x in ("task-id","trace-id","workflow-id","result"):p.add_argument("--"+x,required=True)
 a=p.parse_args()
 if a.task_id!=T or a.workflow_id!=W:raise SystemExit("invalid_identity")
 x=json.loads(Path(a.result).read_text()) if Path(a.result).exists() else {"status":"BLOCKED","task_id":T,"trace_id":a.trace_id,"result":{"blocker":"lifecycle_result_missing"}}
 if not isinstance(x,dict) or x.get("task_id")!=T or x.get("race_id")!=a.trace_id:raise SystemExit("lifecycle_identity_mismatch")
 d=x.get("result") if isinstance(x.get("result"),dict) else {}
 ok=x.get("status")=="STATE_COMMITTED" and d.get("rerminal_state")=="COMPLETED" and d.get("conclusion")=="success"
 rec={"schema_version":1,"protocol":"BEM-949","task_id":T,"created_at":n(),"trace_id":a.trace_id,"status":"PASS" if ok else "BLOCKED","runtime_execution_claim":ok,"target_workflow":W,"lifecycle_result":d,"blockers":[] if ok else [str(d.get("blocker","lifecycle_not_completed"))]}
 put(O,rec)
 if not ok:print(json.dumps(rec));return 1
 q=json.loads(Q.read_text());task=next((z for z in q.get("tasks",[]) if isinstance(z,dict) and z.get("id")==T),None)
 if task is None:raise SystemExit("dsm1_queue_task_missing")
 task.update({"status":"DONE","receipt":str(O.relative_to(R)),"receipt_sha":hashlib.sha256(O.read_bytes())hexdigest(),"receipt_sha_type":"sha256_content","completed_at":n(),"trace_id":a.trace_id});q.update({"current_task":None,"queue_state":"READY","updated_at":n(),"version":int(q.get("version",0) or 0)+1});put(Q,q);print(json.dumps(rec));return 0
if __name__=="__main__":raise SystemExit(main())
