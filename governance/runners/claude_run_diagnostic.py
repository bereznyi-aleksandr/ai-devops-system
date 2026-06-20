#!/usr/bin/env python3
import argparse,json,os,re,subprocess
from datetime import datetime,timezone
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument("--trace-id",required=True);p.add_argument("--head-sha",required=True);p.add_argument("--started-at",required=True)
a=p.parse_args();repo=os.environ["GITHUB_REPOSITORY"];root=Path(__file__).resolve().parents[2]
def gh(x):
 r=subprocess.run(["gh",*x],text=True,capture_output=True,check=False,timeout=180);return r.stdout,r.stderr
raw,_=gh(["run","list","--repo",repo,"--workflow","claude.yml","--limit","100","--json","databaseId,headSha,createdAt,updatedAt,status,conclusion"])
try: rows=json.loads(raw)
except: rows=[]
rows=[x for x in rows if x.get("headSha")==a.head_sha and str(x.get("createdAt",""))>=a.started_at];rows.sort(key=lambda x:str(x.get("createdAt","")),reverse=True);run=rows[0] if rows else {};rid=str(run.get("databaseId",""));step={};log="";err=""
if rid:
 raw,err=gh(["run","view",rid,"--repo",repo,"--json","jobs"])
 try: jobs=json.loads(raw).get("jobs",[])
 except: jobs=[]
 for job in jobs:
  for s in job.get("steps",[]):
   if str(s.get("name","")) in ("Run Claude Code role","Run Claude Code binding role with structured output"):
    step={"job_name":job.get("name"),"job_conclusion":job.get("conclusion"),"step_name":s.get("name"),"step_conclusion":s.get("conclusion"),"step_number":s.get("number")}
    break
  if step: break
 log,e=gh(["run","view",rid,"--repo",repo,"--log"]);err+=e
token=os.environ.get("GH_TOKEN","");log=log.replace(token,"***") if token else log;log=re.sub(r"ghp_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+","***",log)
ls=log.splitlines();ix=set()
for i,x in enumerate(ls):
 q=x.lower()
 if "anthropics/claude-code-action@v1" in q or "run claude code role" in q or any(k in q for k in ("error","failed","failure","exit code","oauth","quota","rate limit","unauthorized","forbidden")):ix.update(range(max(0,i-5),min(len(ls),i+35)))
ex=[ls[i][:900] for i in sorted(ix)][:300];outcome=str(step.get("step_conclusion",""));b=[]
if not rid:b+=["claude_workflow_run_not_found_for_trace_window"]
if not step:b+=["claude_role_step_not_found_in_run_metadata"]
elif outcome!="success":b+=["claude_role_step_conclusion="+(outcome or "unknown")]
if not log.strip():b+=["targeted_action_log_not_accessible"]
reports=root/"governance/reports";reports.mkdir(parents=True,exist_ok=True);rp=reports/(a.trace_id+"_claude_observation.md")
rp.write_text("\n".join(["# BEM-948 P0 Claude run observation","",f"Trace: `{a.trace_id}`",f"Run ID: `{rid}`",f"Workflow conclusion: `{run.get('conclusion','')}`",f"Claude role step: `{step.get('step_name','')}`",f"Claude role step conclusion: `{outcome}`","","## Targeted sanitized excerpt","",*["- `"+x+"`" for x in ex],"","Observation only; no executed/completed P0 result is claimed by this observer."])+"\n",encoding="utf-8")
o={"status":"OBSERVED","protocol":"BEM-948","task_id":"BEM948-P0-CLAUDE-RUN-OBSERVATION","created_at":datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),"trace_id":a.trace_id,"target_head_sha":a.head_sha,"target_head_sha_type":"commit","run":run,"claude_role_step":step,"diagnostic":{"logs_accessible":bool(log.strip()),"targeted_excerpt_lines":len(ex),"log_error_present":bool(err.strip()),"report_path":str(rp.relative_to(root))},"checks":{"observation_is_trace_bound":True,"semantic_step_outcome_checked":True,"no_false_pass_claim":True,"sha_type_explicit":True},"blockers":b,"next_task":"BEM948-P0-REPAIR-CLAUDE-TRANSPORT" if b else "BEM948-P0-POLL-EXECUTED-PROOF"}
proof=root/"governance/proofs/BEM948_p0_claude_run_observation_receipt.json";proof.write_text(json.dumps(o,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");print(json.dumps(o,ensure_ascii=False))
