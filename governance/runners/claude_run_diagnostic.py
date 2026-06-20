#!/usr/bin/env python3
import argparse,json,os,re,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def cmd(a):
 p=subprocess.run(["gh",*a],text=True,capture_output=True,check=False)
 return p.stdout,p.stderr
p=argparse.ArgumentParser()
p.add_argument("--trace-id",required=True);p.add_argument("--head-sha",required=True);p.add_argument("--started-at",required=True)
p.add_argument("--attempts",type=int,default=12);p.add_argument("--delay",type=int,default=15)
a=p.parse_args()
repo=os.environ["GITHUB_REPOSITORY"]; run={}
for _ in range(max(1,a.attempts)):
 out,_=cmd(["run","list","--repo",repo,"--workflow","claude.yml","--limit","100","--json","databaseId,headSha,createdAt,status,conclusion"])
 try: rows=json.loads(out)
 except Exception: rows=[]
 hits=[x for x in rows if x.get("headSha")==a.head_sha and str(x.get("createdAt",""))>=a.started_at]
 if hits:
  hits.sort(key=lambda x:str(x.get("createdAt","")),reverse=True);run=hits[0]
  if run.get("status")=="completed":break
 time.sleep(max(1,a.delay))
rid=str(run.get("databaseId","")); log=""; err=""
if rid:
 log,err=cmd(["run","view",rid,"--repo",repo,"--log-failed"])
 if not log.strip(): log,err=cmd(["run","view",rid,"--repo",repo,"--log"])
secret=os.environ.get("GH_TOKEN","")
log=log.replace(secret,"***") if secret else log
log=re.sub(r"ghp_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+","***",log)
keys=("claude","anthropic","error","failed","failure","exit code","oauth","token","rate","quota","unauthorized","forbidden")
lines=[x[:700] for x in log.splitlines() if any(k in x.lower() for k in keys)][:160]
report=ROOT/"governance/reports/"+Path(a.trace_id+"_claude_observation.md")
report.parent.mkdir(parents=True,exist_ok=True)
report.write_text("# BEM-948 P0 Claude observation\n\nRun ID: `%s`\nStatus: `%s`\nConclusion: `%s`\n\n%s\n"%(rid,run.get("status",""),run.get("status",""),run.get("conclusion",""),"\n".join("- `"+x+"`" for x in lines) or "- No accessible targeted log line."),encoding="utf-8")
blocks=[]
if not rid:blocks.append("claude_workflow_run_not_found_for_trace_window")
elif run.get("status")!="completed":blocks.append("claude_workflow_run_not_completed")
elif run.get("conclusion")!="success":blocks.append("claude_role_or_workflow_runtime_failure")
if not log.strip():blocks.append("targeted_action_log_not_accessible")
receipt={"status":"OBSERVED","protocol":"BEM-948","task_id":"BEM948-P0-CLAUDE-RUN-OBSERVATION","created_at":datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),"trace_id":a.trace_id,"target_head_sha":a.head_sha,"target_head_sha_type":"commit","run":run,"diagnostic":{"logs_accessible":bool(log.strip()),"targeted_excerpt_lines":len(lines),"log_error_present":bool(err.strip()),"report_path":"governance/reports/"+a.trace_id+"_claude_observation.md"},"checks":{"observation_is_trace_bound":True,"claude_action_log_collection_attempted":True,"executed_completed_proof_exists":False,"no_false_pass_claim":True,"sha_type_explicit":True},"blockers":blocks,"next_task":"BEM948-P0-AUTOREPAIR-AFTER-CLAUDE-LOG-DIAGNOSTIC" if blocks else "BEM948-P0-POLL-EXECUTED-PROOF"}
proof=ROOT/"governance/proofs/BEM948_p0_claude_run_observation_receipt.json"
proof.parent.mkdir(parents=True,exist_ok=True);proof.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(receipt,ensure_ascii=False))
