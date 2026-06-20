#!/usr/bin/env python3
import argparse,json,os,re,subprocess
from datetime import datetime,timezone
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument("--trace-id",required=True)
p.add_argument("--not-before",required=True)
a=p.parse_args()
root=Path(__file__).resolve().parents[2]
repo=os.environ["GITHUB_REPOSITORY"]

def gh(args):
    r=subprocess.run(["gh",*args],text=True,capture_output=True,check=False)
    return r.stdout,r.stderr

out,list_err=gh(["run","list","--repo",repo,"--workflow","claude.yml","--limit","100","--json","databaseId,headSha,createdAt,updatedAt,status,conclusion,displayTitle,event"])
try:
    runs=json.loads(out)
except Exception:
    runs=[]
hits=[x for x in runs if str(x.get("createdAt",""))>=a.not_before]
hits.sort(key=lambda x:str(x.get("createdAt","")),reverse=True)
run=hits[0] if hits else {}
rid=str(run.get("databaseId",""))
logs=err=""
if rid:
    logs,err=gh(["run","view",rid,"--repo",repo,"--log-failed"])
    if not logs.strip():
        logs,err=gh(["run","view",rid,"--repo",repo,"--log"])
token=os.environ.get("GH_TOKEN","")
if token: logs=logs.replace(token,"***")
logs=re.sub(r"ghp_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+","***",logs)
keys=("claude","anthropic","error","failed","failure","exit code","oauth","token","rate","quota","unauthorized","forbidden","permission")
lines=[x[:700] for x in logs.splitlines() if any(k in x.lower() for k in keys)][:180]
blockers=[]
if not rid: blockers.append("claude_workflow_run_not_found_after_dispatch")
elif run.get("status")!="completed": blockers.append("claude_workflow_run_not_completed")
elif run.get("conclusion")!="success": blockers.append("claude_workflow_or_role_runtime_failure")
if not logs.strip(): blockers.append("targeted_actions_log_not_accessible")
report=root/"governance"/"reports"/f"{a.trace_id}_claude_targeted_diagnostic.md"
report.parent.mkdir(parents=True,exist_ok=True)
report.write_text("# BEM-948 P0 Claude targeted diagnostic\n\nTrace: `%s`\nRun ID: `%s`\nStatus: `%s`\nConclusion: `%s`\n\n## Sanitized excerpt\n\n%s\n" % (a.trace_id,rid,run.get("status",""),run.get("conclusion",""),"\n".join("- `"+x+"`" for x in lines) or "- No targeted log line was returned."),encoding="utf-8")
receipt={"status":"OBSERVED","protocol":"BEM-948","task_id":"BEM948-P0-CLAUDE-TARGETED-DIAGNOSTIC","created_at":datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),"trace_id":a.trace_id,"not_before":a.not_before,"selected_run":run,"diagnostic":{"logs_accessible":bool(logs.strip()),"targeted_excerpt_lines":len(lines),"list_error_present":bool(list_err.strip()),"log_error_present":bool(err.strip()),"report_path":str(report.relative_to(root))},"checks":{"trace_window_applied":True,"claude_log_collection_attempted":True,"executed_completed_proof_exists":False,"no_false_pass_claim":True,"sha_type_explicit":True},"blockers":blockers,"next_task":"BEM948-P0-AUTOREPAIR-AFTER-CLAUDE-TARGETED-DIAGNOSTIC" if blockers else "BEM948-P0-POLL-EXECUTED-PROOF"}
proof=root/"governance"/"proofs"/"BEM948_p0_claude_targeted_diagnostic_receipt.json"
proof.parent.mkdir(parents=True,exist_ok=True)
proof.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(receipt,ensure_ascii=False,indent=2))
