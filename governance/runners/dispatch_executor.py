#!/usr/bin/env python3
import argparse,json,os,time,urllib.request,urllib.error,urllib.parse
from datetime import datetime,timezone
from pathlib import Path
R=Path(__file__).resolve().parents[2];L=R/"governance/state/dispatch_lifecycle.jsonl";T="BEM949-DSM-1";W="dsm1-lifeycle-probe.yml"
def now():return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def put(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x)+"\n")
def rec(a,s,**x):
 L.parent.mkdir(parents=True,exist_ok=True)
 with L.open("a") as f:f.write(json.dumps({"task_id":T,"trace_id":a.trace_id,"workflow_id":a.workflow_id,"state":s,"observed_at":now(),**x})+"\n")
p=argparse.ArgumentParser()
for n in ("trace-id","dispatch-id","workflow-id","repository","output"):p.add_argument("--"+n,required=True)
p.add_argument("--confirm-only",action="store_true");p.add_argument("--record-dispatched",action="store_true");p.add_argument("--poll-timeout-seconds",type=int,default=300);p.add_argument("--poll-interval-seconds",type=int,default=5)
a=p.parse_args();o=Path(a.output)
def fail(reason,rid=None):
 put(o,{"status":"BLOCKED","task_id":T,"trace_id":a.trace_id,"result":{"blocker":reason,"run_id":rid}});raise SystemExit(1)
if not a.confirm_only or a.dispatch_id!=T or a.workflow_id!=W:fail("invalid_lifecycle_identity")
tok=os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("AI_SYSTEM_GITHUB_PAT") or ""
if not tok or not a.repository:fail("confirm_credentials_repository_or_workflow_missing")
if a.record_dispatched:rec(a,"DISPATCHED",http_status=204)
u=f"https://api.github.com/repos/{a.repository}/actions/workflows/{urllib.parse.quote(W,safe='')}/runs?event=workflow_dispatch&per_page=100";end=time.monotonic()+max(1,a.poll_timeout_seconds);rid=None
while time.monotonic()<end:
 try:
  q=urllib.request.Request(u,headers={"Authorization":"Bearer "+tok,"Accept":"application/vnd.github+json"})
  with urllib.request.urlopen(q,timeout=30) as r:data=json.loads(r.read() or b"{}")
 except Exception:data={}
 run=next((x for x in data.get("workflow_runs",[]) if a.trace_id in " ".join(str(x.get(k) or "") for k in ("display_title","name","path"))),None)
 if run:
  rid=run.get("id",rid);rec(a,"START_CONFIRMED",run_id=rid,github_status=run.get("status"))
  if run.get("status")=="completed":
   c=str(run.get("conclusion") or "unknown");z="COMPLETED" if c=="success" else "FAILED";rec(a,z,run_id=rid,conclusion=c);rec(a,"STATE_COMMITTED",run_id=rid,terminal_state=z,conclusion=c)
   put(o,{"status":"STATE_COMMITTED","task_id":T,"trace_id":a.trace_id,"result":{"terminal_state":z,"conclusion":c,"run_id":rid}});raise SystemExit(0 if c=="success" else 1)
 time.sleep(max(1,a.poll_interval_seconds))
fail
