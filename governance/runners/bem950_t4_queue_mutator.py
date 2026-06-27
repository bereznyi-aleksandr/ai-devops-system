#!/usr/bin/env python3
"""BEM-950 T4 mutator: reclassify P4 and block/record active provider-policy refs."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
R=Path(__file__).resolve().parents[2]
Q=R/"governance/roadmap/ACTIVE_QUEUE.json"
P=R/"governance/proofs"
T1="BEM950-T1-INVALID-WORKFLOW-ARCHIVE";T2="BEM950-T2-PROVIDER-CONFIG-RECLASSIFY";T3="BEM950-T3-RUNNER-FIX-AND-P4-SKIP-LOGIC";T4="BEM950-T4-ACTIVE-QUEUE-P4-RECLASSIFY";S="BEM950-POST-T4-REPOSITORY-WIDE-PROVIDER-SCAN";P4="BEM949-P4-LIVE-LLM-FALLBACK";P7="BEM949-P7-RELEASE-AUDIT-FINAL"
def ts():return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def dump(x):return (json.dumps(x,ensure_ascii=False,indent=2)+"\n").encode()
def sha(b):return hashlib.sha1(b"blob "+str(len(b).encode() + b"\0" + b).hexdigest()
def load(p):
 x=json.loads(p.read_text(encoding="utf-8"))
 if not isinstance(x,dict):raise ValueError(f"JSON object required: {p}")
 return x
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(dump(x))
def main():
 rs={T1:P/"BEM950_t1_workflow_archive_receipt.json",T2:P/"BEM950_t2_provider_config_receipt.json",T3:P/"BEM950_t3_runner_fix_receipt.json"}
 for p in rs.values():
  if not p.is_file() or load(p).get("status")!="PASS":raise SystemExit(f"missing PASS prerequisite: {p}")
 before=Q.read_bytes();q=load(Q);tasks=q.get("tasks")
 if not isinstance(tasks,list):raise ValueError("ACTIVE_QUEUE.tasks must be a list")
 m={t.get("id"):t for t in tasks if isinstance(t,dict) and isinstance(t.get("id"),str)}
 missing=[x for x in (T1,T2,T3,T4,S,P4,P7) if x not in m]
 if missing:raise ValueError(f"missing tasks: {missing}")
 now=ts()
 for k,p in rs.items():m[k].update(status="DONE",completed_at=now,receipt_sha=sha(p.read_bytes()),receipt_sha_type="git_blob")
 m[P4].update(status="SKIPPED_BY_OPERATOR",classification="SUPERSEDED_BY_BEM950_PROVIDER_POLICY",skipped_at="2026-06-27T06:25:00Z",operator_decision="PAID_API_BILLING_CLASS_PROHIBITED",skip_reason="P4 used the prohibited metered OpenAI Responses API path; GPT provider class remains eligible for future non-metered adapters.",note="Allowlisted for P7 audit only; does not establish broad release PASS.")
 policy=q.setdefault("paid_api_policy",{})
 if not isinstance(policy,dict):raise ValueError("paid_api_policy must be an object")
 policy.update(openai_api_key="PERMANENTLY_PROHIBITED",automatic_paid_fallback="PERMANENTLY_PROHIBITED",violation_action="BLOCKED_COST_POLICY",scope_clarification="Prohibition covers metered_api_default and automatic_paid_fallback only. GPT provider-class reactivation via verified subscription, OAuth, or interactive adapter remains valid under BEM-950.")
 m[T4].update(status="DONE",completed_at=now,classification="SUPERSEDED_BY_BEM950_PROVIDER_POLICY")
 q.update(version=max(int(q.get("version",0)),40),current_task=S,queue_state="PENDING",system_status="BEM950_PROVIDER_REFERENCE_SCAN_PENDING",updated_at=now,next_action="Resolve active provider-policy findings before any P7 dispatch.")
 save(Q,q)
 t4={"schema_version":1,"task_id":T4,"created_at":now,"status":"PASS","queue_path":str(Q.relative_to(R)),"queue_sha_before":sha(before),"queue_sha_after":sha(Q.read_bytes()),"sha_type":"git_blob","p4_classification":"SUPERSEDED_BY_BEM950_PROVIDER_POLICY","progress_changed":False}
 save(P/"BEM950_t4_queue_reclassify_receipt.json",t4)
 terms=("OPENAI_API_KEY","OPENAI_MODEL","api.openai.com","gpt_codex_cloud");find=[];active=[]
 for f in sorted((R/".github/workflows").glob("*.y*ml")):
  text=f.read_text(encoding="utf-8",errors="replace");inert=("if: ${{ false }}" in text and "ARCHIVED" in text)
  for n,line in enumerate(text.splitlines(),1):
   for term in terms:
    if term in line:
     d={"path":str(f.relative_to(R)),"line":n,"term":term,"classification":"inert_archive_stub" if inert else "active_workflow"};find.append(d)
     if not inert:active.append(d)
 adapter=R/".github/workflows/provider-adapter.yml"
 if adapter.is_file() and "provider_config.json" not in adapter.read_text(encoding="utf-8",errors="replace"):
  active.append({"path":str(adapter.relative_to(R)),"line":None,"term":"provider_config_policy_not_consulted","classification":"active_workflow_structural"})
 cfg=R/"governance/config/provider_config.json"
 for n,line in enumerate(cfg.read_text(encoding="utf-8",errors="replace").splitlines(),1):
  for term in terms:
   if term in line:find.append({"path":str(cfg.relative_to(R)),"line":n,"term":term,"classification":"provider_config_policy"})
 st="PASS" if not active else "BLOCKED"
 rec={"schema_version":1,"task_id":S,"created_at":now,"status":st,"scope":{"workflow_root":".github/workflows","config_path":str(cfg.relative_to(R)),"terms":list(terms),"archive_directory_excluded":"governance/archive/disabled-workflows"},"sha_type":"git_blob","findings":find,"unresolved_active_findings":active,"blockers":[f"{x['path']}:{x['line']}:{x['term']}" for x in active],"result_rule":"PASS only when active workflow references and adapter behavior conform to cost policy."}
 save(P/"BEM950_provider_reference_scan_receipt.json",rec)
 m[S].update(status="DONE" if st=="PASS" else "BLOCKED",completed_at=now,receipt_sha=sha(dump(rec)),receipt_sha_type="git_blob",blockers=rec["blockers"])
 p7=m[P7];p7["blockers"]=[b for b in p7.get("blockers",[]) if b not in {T1,T2,T3,T4}]
 if st=="PASS":p7["blockers"]=[b for b in p7["blockers"] if b!=S]
 elif S not in p7["blockers"]:p7["blockers"].append(S)
 p7["status"]="BLOCKED_PRECONDITIONS";q["open_blockers"]=p7["blockers"];q["updated_at"]=ts();save(Q,q)
if __name__=="__main__":main()
