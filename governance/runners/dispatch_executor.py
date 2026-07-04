#!/usr/bin/env python3
import argparse,json,os,time,urllib.request,urllib.parse
from pathlib import Path
T="BEM949-DSM-1";W="dsm1-lifeycle-probe.yml"
p=argparse.ArgumentParser()
for x in ("trace-id","dispatch-id","workflow-id","repository","output"):p.add_argument("--"+x,required=True)
p.add_argument("--confirm-only",action="store_true");p.add_argument("--record-dispatched",action="store_true");p.add_argument("--poll-timeout-seconds",type=int,default=300);p.add_argument("--poll-interval-seconds",type=int,default=5)
a=p.parse_args();o=Path(a.output)
def out(s,**r):
 o.parent.mkdir(parents=True,exist_ok=True);o.write_text(json.dumps({"status":s,"task_id":T,"trace_id":a.trace_id,"result":r})+"\n")
def bad(x):out("BLOCKED",blocker=x,run_id=None);raise SystemExit(1)
if not a.confirm_only or a.dispatch_id!=T or a.workflow_id!=W:bad("invalid_lifecycle_identity")
tok=os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("AI_SYSTEM_GITHUB_PAT")
if not tok or not a.repository:bad("confirm_credentials_repository_or_workflow_missing")
u=f"https://api.github.com/repos/{a.repository}/actions/workflows/{urllib.parse.quote(W,safe='')}/runs?event=workflow_dispatch&per_page=100";end=time.monotonic()+max(1,a.poll_timeout_seconds);rid=None
while time.monotonic()<end:
 try:
  q=urllib.request.Request(u,headers={"Authorization":"Bearer "+tok,"Accept":"application/vnd.github+json"})
  with urllib.request.urlopen(q,timeout=30) as h:d=json.loads(h.read() or b"{}")
 except Exception:d={}
 r=next((x for x in d.get("workflow_runs",[]) if a.trace_id in " ".join(str(x.get(k)or"")for k in("display_title","name","path"))),None)
 if r and r.get("status")=="completed":
  rid=r.get("id");c=str(r.get("conclusion")or"unknown");z="COMPLETED" if c=="success" else "FAILED";out("STATE_COMMITTED",terminal_state=z,conclusion=c,run_id=rid);raise SystemExit(0 if c=="success" else 1)
 time.sleep(max(1,a.poll_interval_seconds))
bad("start_or_terminal_state_not_observed_before_timeout")
