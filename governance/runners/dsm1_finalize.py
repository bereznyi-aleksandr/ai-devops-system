#!/usr/bin/env python3
"""Finalize a BEM-949 DSM-1 Actions-lifecycle observation."""
import argparse, hashlib, json, uuid
from datetime import datetime, timezone
from pathlib import Path
def now(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--task-id",required=True);p.add_argument("--trace-id",required=True)
    p.add_argument("--workflow-id",required=True);p.add_argument("--result",required=True)
    a=p.parse_args()
    result_path=Path(a.result);result=json.loads(result_path.read_text()) if result_path.exists() else {"status":"BLOCKED","result":{"state":"FAILED","blocker":"lifecycle_result_missing"}}
    detail=result.get("result",{});success=result.get("status")=="STATE_COMMITTED" and detail.get("terminal_state")=="COMPLETED" and detail.get("conclusion")=="success"
    stamp=now();receipt_path=Path("governance/proofs/BEM949_dsm1_runtime_hardening_receipt.json")
    receipt={"schema_version":1,"protocol":"BEM-949","task_id":a.task_id,"created_at":stamp,"trace_id":a.trace_id,
      "status":"PASS" if success else "BLOCKED","runtime_execution_claim":success,
      "evidence_kind":"github_actions_api_lifecycle_poll","executor_path":"governance/runners/dispatch_executor.py",
      "autopilot_path":".github/workflows/roadmap-autopilot.yml","target_workflow":a.workflow_id,
      "lifecycle_result":detail,
      "acceptance":{"http_204_not_treated_as_completion":True,"dispatched_to_start_confirmed_to_terminal_observed":success,"state_committed_recorded":success},
      "blockers":[] if success else [detail.get("blocker","lifecycle_not_completed")]}
    receipt_path.parent.mkdir(parents=True,exist_ok=True);receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    if success:
      qp=Path("governance/roadmap/ACTIVE_QUEUE.json");before=qp.read_bytes();q=json.loads(before)
      task=next(t for t in q["tasks"] if t.get("id")==a.task_id)
      task.update({"status":"DONE","receipt":str(receipt_path),"receipt_sha":hashlib.sha256(receipt_path.read_bytes()).hexdigest(),"receipt_sha_type":"sha256_content","completed_at":stamp,"trace_id":a.trace_id})
      q["current_task"]=None;q["updated_at"]=stamp;q["version"]=int(q.get("version",0))+1
      q["progress"]["tasks_done"]=int(q["progress"]["tasks_done"])+1
      q["progress"]["percent"]=round(q["progress"]["tasks_done"]/q["progress"]["tasks_total"]*100,1)
      qp.write_text(json.dumps(q,ensure_ascii=False,indent=2)+"\n");after=qp.read_bytes()
      lp=Path("governance/state/ssot_transaction_log.jsonl");lp.parent.mkdir(parents=True,exist_ok=True)
      txn={"state_change_id":str(uuid.uuid4()),"trace_id":a.trace_id,"target_ssot_file":str(qp),
           "pre_state_hash":"sha256:"+hashlib.sha256(before).hexdigest(),"post_state_hash":"sha256:"+hashlib.sha256(after).hexdigest(),
           "receipt_ref":str(receipt_path),"applied_by":"roadmap-autopilot","applied_at":stamp,"rollback_rule":"REVERT_TO_PRE_STATE_HASH"}
      with lp.open("a",encoding="utf-8") as f:f.write(json.dumps(txn,ensure_ascii=False)+"\n")
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
