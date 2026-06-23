#!/usr/bin/env python3
"""BEM-949 P7 runtime audit."""
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path

STAGES=(
 "BEM949-P0.5-TEXT-INTEGRITY-FIX","BEM949-P1-CI-STABILIZE",
 "BEM949-P2-FUNCTIONAL-RESTORE","BEM949-P3-ALL-ROLE-E2E",
 "BEM949-P4-LIVE-LLM-FALLBACK","BEM949-P5-RULE-ENFORCEMENT-COMPLETE",
 "BEM949-P6-LEARNING-LOOP-DRILL")
P6="BEM949-P6-LEARNING-LOOP-DRILL"
P7="BEM949-P7-RELEASE-AUDIT-FINAL"

def now():
 return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def load(path):
 x=json.loads(Path(path).read_text(encoding="utf-8"))
 if not isinstance(x,dict): raise ValueError("JSON object required: "+str(path))
 return x

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def proof(path):
 if not isinstance(path,str) or not path: return None,None,"missing_receipt_path"
 p=Path(path)
 if not p.is_file(): return None,None,"missing_receipt"
 try: status=load(p).get("status")
 except (OSError,UnicodeDecodeError,json.JSONDecodeError,ValueError) as exc:
  return None,None,"unreadable_receipt:"+type(exc).__name__
 return (status if isinstance(status,str) else None,digest(p),
         None if isinstance(status,str) else "missing_receipt_status")

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--queue",default="governance/roadmap/ACTIVE_QUEUE.json")
 ap.add_argument("--out",default="governance/proofs/BEM949_p7_external_release_audit_receipt.json")
 ap.add_argument("--trace-id",default="bem949_p7_release_audit")
 a=ap.parse_args()
 qp=Path(a.queue); q=load(qp); tasks=q.get("tasks")
 if not isinstance(tasks,list): raise ValueError("ACTIVE_QUEUE.tasks must be a list")
 by={x.get("id"):x for x in tasks if isinstance(x,dict) and isinstance(x.get("id"),str)}
 if P6 not in by or P7 not in by: raise ValueError("P6 or P7 task missing")
 s,h,e=proof(by[P6].get("receipt"))
 if s!="PASS": raise ValueError("P6 receipt is not PASS: "+str(s or e))
 by[P6].update(status="DONE",completed_at=now(),receipt_sha=h,receipt_sha_type="sha256_content")
 checks=[]; blockers=[]
 for ident in STAGES:
  task=by.get(ident)
  if task is None:
   checks.append({"task_id":ident,"present":False,"clean_done":False})
   blockers.append("missing_task:"+ident); continue
  rs,rh,re=proof(task.get("receipt")); qs=str(task.get("status",""))
  clean=qs=="DONE" and rs=="PASS"
  checks.append({"task_id":ident,"queue_status":qs,"receipt_status":rs,
                 "receipt_sha":rh,"receipt_sha_type":"sha256_content" if rh else None,
                 "receipt_error":re,"clean_done":clean})
  if not clean: blockers.append(f"stage_not_clean_done:{ident}:queue={qs}:receipt={rs or re or 'unknown'}")
 passed=not blockers
 rec={"schema_version":1,"protocol":"BEM-949","task_id":P7,
      "receipt_id":"BEM949_p7_external_release_audit","created_at":now(),
      "trace_id":a.trace_id,"evidence_kind":"independent_runtime_audit",
      "runtime_execution_claim":True,
      "execution":{"runner_path":"governance/runners/bem949_release_audit_runner.py",
                   "runner_sha":digest(Path(__file__).resolve()),"runner_sha_type":"sha256_content",
                   "queue_path":str(qp),"queue_sha":digest(qp),"queue_sha_type":"sha256_content"},
      "checks":checks,"blockers":[],
      "acceptance":{"all_p05_to_p6_clean_done":passed,"limitations_absent":passed,
                    "broad_release_pass_claimed":passed},
      "non_claim":"BLOCKED is an executed independent audit observation, not a Release PASS.",
      "status":"PASS" if passed else "BLOCKED"}
 out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(rec,ensure_ascii=True,indent=2)+"\n",encoding="utf-8")
 p7=by[P7]; p7.update(status="DONE" if passed else "BLOCKED",completed_at=now(),
                      receipt_sha=digest(out),receipt_sha_type="sha256_content")
 q.update(current_task=None,queue_state="COMPLETE" if passed else "BLOCKED",
          system_status="BEM949_RELEASE_AUDIT_PASS" if passed else "BEM949_RELEASE_AUDIT_BLOCKED",
          release_status="PASS" if passed else "VERIFIED_WITH_LIMITATIONS",
          next_action="Roadmap complete." if passed else "Resume only recorded blockers; do not claim broad Release PASS.",
          updated_at=now())
 prog=q.get("progress")
 if isinstance(prog,dict):
  n=sum(1 for x in tasks if isinstance(x,dict) and str(x.get("status","")).startswith("DONE"))
  prog["tasks_done"]=n
  if isinstance(prog.get("tasks_total"),int) and prog["tasks_total"]:
   prog["percent"]=round(n*100/prog["tasks_total"],2)
 qp.write_text(json.dumps(q,ensure_ascii=True,indent=2)+"\n",encoding="utf-8")
 print(json.dumps(rec,ensure_ascii=True))
 return 0

if __name__=="__main__": raise SystemExit(main())
