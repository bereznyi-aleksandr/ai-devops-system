#!/usr/bin/env python3
"""Trace-bound GitHub Actions lifecycle observer for BEM949-DSM-1."""
import argparse,json,os,time,urllib.error,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
LOG=ROOT/"governance/state/dispatch_lifecycle.jsonl"
TASK="BEM949-DSM-1"
WORKFLOW="dsm1-lifecycle-probe.yml"
def now(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def emit(trace,workflow,state,**extra):
    LOG.parent.mkdir(parents=True,exist_ok=True)
    item={"protocol":"BEM-949","task_id":TASK,"observed_at":now(),"trace_id":trace,"workflow_id":workflow,"state":state,**extra}
    with LOG.open("a",encoding="utf-8") as handle: handle.write(json.dumps(item,ensure_ascii=False,sort_keys=True)+"\n")
def fetch(url,token):
    request=urllib.request.Request(url,headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json","User-Agent":"ai-devops-dsm1"})
    try:
        with urllib.request.urlopen(request,timeout=30) as response:
            body=response.read().decode("utf-8","replace")
            data=json.loads(body) if body else {}
            return response.status,data if isinstance(data,dict) else {}
    except urllib.error.HTTPError as exc: return exc.code,{}
    except Exception as exc: return 0,{"error":type(exc).__name__}
p=argparse.ArgumentParser()
p.add_argument("--confirm-only",action="store_true")
p.add_argument("--record-dispatched",action="store_true")
p.add_argument("--trace-id",required=True)
p.add_argument("--dispatch-id",required=True)
p.add_argument("--workflow-id",required=True)
p.add_argument("--repository",required=True)
p.add_argument("--poll-timeout-seconds",type=int,default=300)
p.add_argument("--poll-interval-seconds",type=int,default=5)
p.add_argument("--output",required=True)
a=p.parse_args(); out=Path(a.output)
def blocked(reason,run_id=None,http_status=None):
    result={"status":"BLOCKED","task_id":TASK,"trace_id":a.trace_id,"result":{"blocker":reason,"run_id":run_id}}
    if http_status is not None: result["result"]["last_http_status"]=http_status
    save(out,result); raise SystemExit(1)
if not a.confirm_only: blocked("confirm_only_required")
if a.dispatch_id!=TASK: blocked("dispatch_id_must_be_BEM949_DSM_1")
if a.workflow_id!=WORKFLOW: blocked("workflow_id_must_be_dsm1_lifecycle_probe")
token=os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("AI_SYSTEM_GITHUB_PAT") or ""
if not token or not a.repository: blocked("confirm_credentials_repository_or_workflow_missing")
if a.record_dispatched: emit(a.trace_id,a.workflow_id,"DISPATCHED",http_status=204)
encoded=urllib.parse.quote(a.workflow_id,safe="")
url=f"https://api.github.com/repos/{a.repository}/actions/workflows/{encoded}/runs?event=workflow_dispatch&per_page=100"
deadline=time.monotonic()+max(1,a.poll_timeout_seconds); observed=None; last=None
while time.monotonic()<deadline:
    last,data=fetch(url,token)
    runs=data.get("workflow_runs",[]) if last==200 else []
    candidate=next((run for run in runs if isinstance(run,dict) and a.trace_id in " ".join(str(run.get(key) or "") for key in ("display_title","name","path"))),None)
    if candidate:
        if observed is None:
            observed=candidate.get("id")
            emit(a.trace_id,a.workflow_id,"START_CONFIRMED",run_id=observed,github_status=candidate.get("status"),html_url=candidate.get("html_url"))
        if candidate.get("status")=="completed":
            conclusion=str(candidate.get("conclusion") or "unknown")
            terminal="COMPLETED" if conclusion=="success" else "FAILED"
            emit(a.trace_id,a.workflow_id,terminal,run_id=observed,conclusion=conclusion,html_url=candidate.get("html_url"))
            emit(a.trace_id,a.workflow_id,"STATE_COMMITTED",run_id=observed,terminal_state=terminal,conclusion=conclusion,commit_scope="dispatch_lifecycle_log")
            save(out,{"status":"STATE_COMMITTED","task_id":TASK,"trace_id":a.trace_id,"result":{"terminal_state":terminal,"conclusion":conclusion,"run_id":observed,"html_url":candidate.get("html_url")}})
            raise SystemExit(0 if conclusion=="success" else 1)
    time.sleep(max(1,a.poll_interval_seconds))
blocked("start_or_terminal_state_not_observed_before_timeout",observed,last)
