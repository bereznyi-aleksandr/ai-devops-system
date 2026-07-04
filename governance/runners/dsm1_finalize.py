#!/usr/bin/env python3
"""Identity-bound DSM-1 lifecycle finalizer."""
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path

TASK="BEM949-DSM-1"; WORKFLOW="dsm1-lifecycle-probe.yml"
ROOT=Path(__file__).resolve().parents[2]
RECEIPT=ROOT/"governance/proofs/BEM949_dsm1_runtime_execution_receipt.json"
QUEUE=ROOT/"governance/roadmap/ACTIVE_QUEUE.json"
def now():return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def read_result(p,trace):
    if not p.exists():return {"status":"BLOCKED","task_id":TASK,"trace_id":trace,"result":{"blocker":"lifecycle_result_missing"}}
    x=json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(x,dict):raise SystemExit("lifecycle_result_not_object")
    return x
def find(q):
    for x in q.get("tasks",[]):
        if isinstance(x,dict) and x.get("id")==TASK:return x
    raise SystemExit("dsm1_queue_task_missing")
def main():
    p=argparse.ArgumentParser();p.add_argument("--task-id",required=True);p.add_argument("--trace-id",required=True);p.add_argument("--workflow-id",required=True);p.add_argument("--result",required=True);a=p.parse_args()
    if a.task_id!=TASK:raise SystemExit("task_id_must_be_BEM949_DSM_1")
    if a.workflow_id!=WORKFLOW:raise SystemExit("workflow_id_must_be_dsm1_lifecycle_probe_yml")
    lifecycle=read_result(Path(a.result),a.trace_id)
    if lifecycle.get("task_id")!=TASK:raise SystemExit("lifecycle_result_task_id_mismatch")
    if lifecycle.get("trace_id")!=a.trace_id:raise SystemExit("lifecycle_result_trace_id_mismatch")
    detail=lifecycle.get("result");detail=detail if isinstance(detail,dict) else {}
    passed=lifecycle.get("status")=="STATE_COMMITTED" and detail.get("rerminal_state")=="COMPLETED" and detail.get("conclusion")=="success"
    receipt={"schema_version":1,"protocol":"BEM-949","task_id":TASK,"created_at":now(),"trace_id":a.trace_id,"status":"PASS" if passed else "BLOCKED","runtime_execution_claim":passed,"evidence_kind":"github_actions_api_lifecycle_poll","target_workflow":WORKFLOW,"lifecycle_result":detail,"acceptance":{"http_204_not_treated_as_completion":True,"dispatched_to_start_confirmed_to_terminal_observed":passed,"state_committed_recorded":passed,"task_identity_bound":True,"workflow_identity_bound":True,"trace_identity_bound":True},"blockers":[] if passed else [str(detail.get("blocker","lifecycle_not_completed"))]}
    save(RECEIPT,receipt)
    if not passed:print(json.dumps(receipt,ensure_ascii=False,indent=2));return 1
    q=json.loads(QUEUE.read_text(encoding="utf-8"))
    if not isinstance(q,dict):raise SystemExit("queue_not_object")
    t=find(q);t.update({"status":"DONE","receipt":str(RECEIPT.relative_to(ROOT)),"receipt_sha":hashlib.sha256(RECEIPT.read_bytes()).hexdigest(),"receipt_sha_type":"sha256_content","completed_at":now(),"trace_id":a.trace_id})
    q.update({"current_task":None,"queue_state":"READY","updated_at":now(),"version":int(q.get("version",0) or 0)+1});save(QUEUE,q)
    print(json.dumps(receipt,ensure_ascii=False,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
