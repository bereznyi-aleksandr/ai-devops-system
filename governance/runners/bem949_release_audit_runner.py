#!/usr/bin/env python3
"""BEM-949 P7 runtime audit."""
import argparse,json,hashlib
from datetime import datetime,timezone
from pathlib import Path

S=("BEM949-P0.5-TEXT-INTEGRITY-FIX","BEM949-P1-CI-STABILIZE",
"BEM949-P2-FUNCTIONAL-RESTORE","BEM949-P3-ALL-ROLE-E2E",
"BEM949-P4-LIVE-LLM-FALLBACK","BEM949-P5-RULE-ENFORCEMENT-COMPLETE",
"BEM949-P6-LEARNING-LOOP-DRILL")
P6=S[-1];P7="BEM949-P7-RELEASE-AUDIT-FINAL"
def now():return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def load(p):
 x=json.loads(Path(p).read_text(encoding="utf-8"))
 if not isinstance(x,dict):raise ValueEror("JSON object required: "+str(path))
 return x
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def status(p):
 if not isinstance(p,str)or not p:return None,None,"missing_receipt_path"
 p=Path(p)
 if not p.is_file():return None,None,"missing_receipt"
 try:s=load(p).get("status")
 except(Exception)as e:return None,None,"unreadable:"+type(e).__name__
 return(s if isinstance(s,str)else None,sha(p),None if isinstance(s,str)else"missing_receipt_status")
def main():
 a=argparse.ArgumentParser();a.add_argument("--queue",default="governance/roadmap/ACTIVE_QUEUE.json");a.add_argument("--out",default="governance/proofs/BEM949_p7_external_release_audit_receipt.json");a.add_argument("--trace-id",default="bem949_p7_release_audit");a=a.parse_args()
 qp=Path(a.queue);q=load(qp);ts=q.get("tasks")
 if not isinstance(ts,list):raise ValueError("ACTIVE_QUE.tasks must be a list")
 by={x.get("id"):x for x in ts if isinstance(x,dict)and isinstance(x.get("id"),str)}
 if P6 not in by or P7 not in by:raise ValueError("P6 or P7 task missing")
 ps,ph,pe=status(by[P6].get("receipt"))
 if ps!="PASS":raise ValueError("P6 receipt is not PASS: "+str(ps or pe))
 by[P6].update(status="DONE",completed_at=now(),receipt_sha=ph,receipt_sha_type="sha256_content")
 checks=[];blockers=[]
 for k in S:
  t=by.get(k)
  if t is None:checks.append({"task_id":k,"clean_done":False,"reason":"missing_task"});blockers.append("missing_task:"+k);continue
  rs,rh,re=status(t.get("receipt"));qs=str(t.get("status",""));ok=qs=="DONE"and rs=="PASS"
  checks.append({"task_id":k,"queue_status":qs,"receipt_status":rs,"receipt_sha":rh,"receipt_error":re,"clean_done":ok})
  if not ok:blockers.append(f"stage_not_clean_done:{k}:queue={qs}:receipt={rs or re or 'unknown'}")
 passed=not blockers
 rec={"schema_version":1,"protocol":"BEM-949","task_id":P7,"receipt_id":"BEM949_p7_external_release_audit","created_at":now(),"trace_id":a.trace_id,"evidence_kind":"independent_runtime_audit","runtime_execution_claim":True,"execution":{"runner_path":"governance/runners/bem949_release_audit_runner.py","runner_sha":sha(Path(__file__).resolve()),"runner_sha_type":"sha256_content","queue_sha":sha(qp),"queue_sha_type":"sha256_content"},"checks":checks,"blockers":blockers,"acceptance":{"all_p05_to_p6_clean_done":passed,"limitations_absent":passed,"broad_release_pass_claimed":passed},"status":"PASS"if passed else"BLOCKED"}
 out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(rec,ensure_ascii=True,indent=2)+"\n",encoding="utf-8")
 by[P7].update(status="DONE"if passed else"BLOCKED",completed_at=now(),receipt_sha=sha(out),receipt_sha_type="sha256_content")
 q.update(current_task=None,queue_state="COMPLETE"if passed else"BLOCKED",system_status="BEM949_RELEASE_AUDIT_PASS"if passed else"BEM949_RELEASE_AUDIT_BLOCKED",release_status="PASS"if passed else"VERIFIED_WITH_LIMITATIONS",next_action="Roadmap complete."if passed else"Resume only recorded blockers; do not claim broad Release PASS.",updated_at=now())
 p=q.get("progress")
 if isinstance(p,dict):
  n=sum(1 for x in ts if isinstance(x,dict)and str(x.get("status","")).startswith("DONE"));p["tasks_done"]=n
  if isinstance(p.get("tasks_total"),int)and p["tasks_total"]:p["percent"]=round(n*100/p["tasks_total"],2)
 qp.write_text(json.dumps(q,ensure_ascii=True,indent=2)+"\n",encoding="utf-8");print(json.dumps(rec,ensure_ascii=True));return 0
if __name__=="__main__":raise SystemExit(main())
