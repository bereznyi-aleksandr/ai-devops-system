#!/usr/bin/env python3
import argparse,json,os,time,urllib.error,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path
T="BEM949-DSM-1";W="dsm1-lifecycle-probe.yml"
R=Path(__file__).resolve().parents[2];L=R/"governance/state/dispatch_lifecycle.jsonl"
p=argparse.ArgumentParser()
p.add_argument("--confirm-only",action="store_true");p.add_argument("--record-dispatched",action="store_true")
for n in ("trace-id","dispatch-id","workflow-id","repository","output"):p.add_argument("--"+n,required=True)
p.add_argument("--poll-timeout-seconds",type=int,default=300);p.add_argument("--poll-interval-seconds",type=int,default=5)
a=p.parse_args();o=Path(a.output)
def put(x):
 o.parent.mkdir(parents=True,exist_ok=True);o.write_text(json.dumps(x,indent=2)+"\n")
def fail(reason,rid=None,http=None):
 x={"status":"BLOCKED","task_id":T,"trace_id":a.trace_id,"result":{"blocker":reason,"run_id":rid}}
 if http is not None:x["result"]["last_http_status"]=http
 put(x);raise SystemExit(1)
def evt(state,**x):
 L.parent.mkdir(parents=True,exist_ok=True)
 v={"protocol":"BEM-949","task_id":T,"observed_at":datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),"trace_id":a.trace_id,"workflow_id":W,"state":state,**x}
 with L.open("a") as h:h.write(json.dumps(v,sort_keys=True)+"\n")
if not a.confirm_only:fail("confirm_only_required")
if a.dispatch_id!=T or a.workflow_id!=W:fail("invalid_lifecycle_identity")
tok=os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("AI_SYSTEM_GITHUB_PAT")
if not tok or not a.repository:fail("confirm_credentials_repository_or_workflow_missing")
if a.record_dispatched:evt("DISPATCHED",http_status=204)
u=f"{os.getenv('GITHUB_API_URL','https://api.github.com').rstrip('/')}/repos/{a.repository}/actions/workflows/{urllib.parse.quote(W,safe='')}/runs?event=workflow_dispatch&per_page=100"
end=time.monotonic()+max(1,a.poll_timeout_seconds);rid=None;last=None
while time.monotonic()<end:
 try:
  q=urllib.request.Request(u,headers={"Authorization":f"Bearer {tok}","Accept":"application/vnd.github+json"})
  with urllib.request.urlopen(q,timeout=30) as h:last=h.status;d=json.loads(h.read().decode() or "{}")
 except urllib.error.HTTPError as e:last=e.code;d={}
 except Exception:d={}
 runs=d.get("workflow_runs",[]) if last==200 and isinstance(d,dict) else []
 run=next((x for x in runs if isinstance(x,dict) and a.trace_id in " ".join(str(x.get(k)or"") for k in ("display_title","name","path"))),None)
 if run:
  ident=run.get("id")
  if isinstance(ident,int) and rid is None:rid=ident;evt("START_CONFIRMED",run_id=rid,github_status=run.get("status"),html_url=run.get("html_url"))
  if run.get("status")=="completed":
   c=str(run.get("conclusion")or"unknown");z="COMPLETED" if c=="success" else "FAILED"
   evt(z,run_id=rid,conclusion=c,html_url=run.get("html_url"));evt("STATE_COMMITTED",run_id=rid,terminal_state=z,conclusion=c,commit_scope="dispatch_lifecycle_log")
   put({"status":"STATE_COMMITTED","task_id":T,"trace_id":a.trace_id,"result":{"terminal_state":z,"conclusion":c,"run_id":rid,"html_url":run.get("html_url")}})
   raise SystemExit(0 if c=="success" else 1)
 time.sleep(max(1,a.poll_interval_seconds))
fail("start_or_terminal_state_not_observed_before_timeout",rid,last)
