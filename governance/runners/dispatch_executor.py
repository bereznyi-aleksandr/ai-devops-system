#!/usr/bin/env python3
"""BEM-949 DSM-1: HTTP 204 is dispatch acknowledgement, never completion."""
import argparse,json,os,time,urllib.error,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
DPRO=ROOT/"governance/state/dispatch_processed.jsonl"
DEXE=ROOT/"governance/state/dispatch_executed.jsonl"
DLIF=ROOT/"governance/state/dispatch_lifecycle.jsonl"
DOUT=ROOT/"governance/proofs/BEM948_dispatch_executor_receipt.json"
TARGETS={"claude_code":"claude.yml","gpt_codex_cloud":"gpt-codex-cloud.yml"}
def now(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def load(p):
    if not p.exists(): return []
    out=[]
    for x in p.read_text(encoding="utf-8",errors="replace").splitlines():
        try:
            v=json.loads(x)
            if isinstance(v,dict): out.append(v)
        except json.JSONDecodeError: pass
    return out
def append(p,vals):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("a",encoding="utf-8") as f:
        for v in vals: f.write(json.dumps(v,ensure_ascii=False,sort_keys=True)+"\n")
def dump(p,v):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def api(url,tok,method="GET",body=None):
    data=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request(url,data=data,method=method,headers={"Authorization":"Bearer "+tok,"Accept":"application/vnd.github+json","Content-Type":"application/json","User-Agent":"ai-devops-dsm1"})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            raw=r.read().decode("utf-8","replace");return r.status,json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        try:return e.code,json.loads(e.read().decode("utf-8","replace"))
        except json.JSONDecodeError:return e.code,{}
    except Exception as e:return 0,{"error":type(e).__name__}
def evt(trace,did,wf,state,**kw):
    return {"protocol":"BEM-949","task_id":"BEM949-DSM-1","observed_at":now(),"trace_id":trace,"dispatch_id":did,"workflow_id":wf,"state":state,**kw}
def inputs(row,trace,provider):
    tid=str(row.get("task_id") or "BEM948-DISPATCH")
    if provider=="gpt_codex_cloud":return {"trace_id":trace,"task_id":tid}
    p=row.get("payload") if isinstance(row.get("payload"),dict) else {}
    return {"role":str(row.get("logical_role") or row.get("role") or "curator"),"provider":"claude","trace_id":trace,"cycle_id":str(p.get("cycle_id") or "dispatch_"+trace),"task_type":str(p.get("task_type") or "default_development"),"task":str(p.get("task") or "Governance dispatch "+trace)}
def poll(trace,did,wf,repo,tok,timeout,interval,lif):
    apiroot=os.getenv("GITHUB_API_URL","https://api.github.com").rstrip("/")
    until=time.monotonic()+timeout;runid=None
    url=f"{apiroot}/repos/{repo}/actions/workflows/{urllib.parse.quote(wf,safe='')}/runs?event=workflow_dispatch&per_page=100"
    while time.monotonic()<until:
        status,payload=api(url,tok)
        candidates=payload.get("workflow_runs",[]) if status==200 and isinstance(payload,dict) else []
        run=next((r for r in candidates if isinstance(r,dict) and trace in " ".join(str(r.get(k) or "") for k in ("display_title","name","path"))),None)
        if run:
            rid=run.get("id")
            if isinstance(rid,int) and runid is None:
                runid=rid;append(lif,[evt(trace,did,wf,"START_CONFIRMED",run_id=runid,github_status=run.get("status"),html_url=run.get("html_url"))])
            if run.get("status")=="completed":
                c=str(run.get("conclusion") or "unknown"); term="COMPLETED" if c=="success" else "FAILED"
                append(lif,[evt(trace,did,wf,term,run_id=runid,conclusion=c,html_url=run.get("html_url")),evt(trace,did,wf,"STATE_COMMITTED",run_id=runid,terminal_state=term,conclusion=c,commit_scope="dispatch_lifecycle_log")])
                return {"state":"STATE_COMMITTED","terminal_state":term,"run_id":runid,"conclusion":c,"html_url":run.get("html_url")}
        time.sleep(interval)
    b="start_or_terminal_state_not_observed_before_timeout";append(lif,[evt(trace,did,wf,"FAILED",blocker=b,run_id=runid)])
    return {"state":"FAILED","blocker":b,"run_id":runid}
def dispatch(row,trace,a,lif):
    provider=str(row.get("provider_selected") or row.get("provider") or "");wf=str(row.get("target_workflow_id") or "");did=str(row.get("dispatch_id") or row.get("trace_id") or "")
    out={"protocol":"BEM-948","task_id":str(row.get("task_id") or "BEM948-DISPATCH"),"created_at":now(),"dispatch_id":did,"trace_id":trace,"provider_selected":provider,"target_workflow_id":wf,"dispatch_result":"failed","http_status":None,"blocker":None}
    if TARGETS.get(provider)!=wf:out["blocker"]="unsupported_or_mismatched_provider_target";return out
    tok=os.getenv("AI_SYSTEM_GITHUB_PAT") or os.getenv("GITHUB_TOKEN") or "";repo=os.getenv("GITHUB_REPOSITORY") or a.repository
    if not tok or not repo:out["blocker"]="github_dispatch_credentials_or_repository_missing";return out
    inp=inputs(row,trace,provider);out["inputs"]=inp
    st,_=api(f"{os.getenv('GITHUB_API_URL','https://api.github.com').rstrip('/')}/repos/{repo}/actions/workflows/{urllib.parse.quote(wf,safe='')}/dispatches",tok,"POST",{"ref":"main","inputs":inp});out["http_status"]=st
    if st!=204:out["blocker"]="workflow_dispatch_http_"+str(st);return out
    out["dispatch_result"]="dispatched";append(lif,[evt(trace,did,wf,"DISPATCHED",http_status=204)])
    out["lifecycle"]=poll(trace,did,wf,repo,tok,a.poll_timeout_seconds,a.poll_interval_seconds,lif)
    if out["lifecycle"]["state"]!="STATE_COMMITTED":out["dispatch_result"]="failed";out["blocker"]=out["lifecycle"]["blocker"]
    return out
def main():
    p=argparse.ArgumentParser();p.add_argument("--trace-id",required=True);p.add_argument("--plan-file");p.add_argument("--max",type=int,default=1);p.add_argument("--processed",default=str(DPRO));p.add_argument("--executed",default=str(DEXE));p.add_argument("--lifecycle",default=str(DLIF));p.add_argument("--output",default=str(DOUT));p.add_argument("--repository",default="");p.add_argument("--confirm-only",action="store_true");p.add_argument("--record-dispatched",action="store_true");p.add_argument("--workflow-id",default="");p.add_argument("--dispatch-id",default="");p.add_argument("--poll-timeout-seconds",type=int,default=300);p.add_argument("--poll-interval-seconds",type=int,default=5)
    a=p.parse_args();trace=a.trace_id.strip();lif=Path(a.lifecycle)
    if not trace:raise SystemExit("trace_id_required")
    if a.confirm_only:
        tok=os.getenv("AI_SYSTEM_GITHUB_PAT") or os.getenv("GITHUB_TOKEN") or "";repo=a.repository or os.getenv("GITHUB_REPOSITORY") or "";did=a.dispatch_id or trace
        if not tok or not repo or not a.workflow_id: r={"state":"FAILED","blocker":"confirm_credentials_repository_or_workflow_missing"}
        else:
            if a.record_dispatched:append(lif,[evt(trace,did,a.workflow_id,"DISPATCHED",http_status=204)])
            r=poll(trace,did,a.workflow_id,repo,tok,a.poll_timeout_seconds,a.poll_interval_seconds,lif)
        receipt={"status":"STATE_COMMITTED" if r["state"]=="STATE_COMMITTED" else "BLOCKED","protocol":"BEM949","task_id":"BEM949-DSM-1","created_at":now(),"evidence_kind":"github_actions_api_polling","runtime_execution_claim":r["state"]=="STATE_COMMITTED","result":r};dump(Path(a.output),receipt);print(json.dumps(receipt,ensure_ascii=False,indent=2));raise SystemExit(0 if r["state"]=="STATE_COMMITTED" else 1)
    try:
        if a.plan_file:
            row=json.loads(Path(a.plan_file).read_text());src=[row] if isinstance(row,dict) and str(row.get("trace_id") or "")==trace and str(row.get("dispatch_result") or "planned")=="planned" else []
        else:
            done={str(x.get("dispatch_id") or x.get("trace_id") or "") for x in load(Path(a.executed))}
            src=[x for x in load(Path(a.processed)) if x.get("status")=="processed" and x.get("dispatch_result")=="planned" and str(x.get("trace_id") or x.get("dispatch_id") or "")==trace and str(x.get("dispatch_id") or x.get("trace_id") or "") not in done][:max(1,a.max)]
    except Exception:src=[]
    if not src:
        receipt={"status":"BLOCKED","protocol":"BEM-948","task_id":"BEM948-DISPATCH","created_at":now(),"trace_filter":trace,"dispatches":[],"blockers":["matching_planned_dispatch_absent"]};dump(Path(a.output),receipt);print(json.dumps(receipt,ensure_ascii=False,indent=2));raise SystemExit(1)
    out=[dispatch(x,trace,a,lif) for x in src];append(Path(a.executed),out);bad=[x for x in out if x["dispatch_result"]!="dispatched"]
    receipt={"status":"STATE_COMMITTED" if not bad else "BLOCKED","protocol":"BEM-949","task_id":str(src[0].get("task_id") or "BEM948-DISPATCH"),"created_at":now(),"trace_filter":trace,"evidence_kind":"github_actions_api_polling","dispatches":out,"checks":{"http_204_not_completion":True,"start_confirmed_polling":True},"blockers":[x["blocker"] for x in bad if x.get("blocker")]};dump(Path(a.output),receipt);print(json.dumps(receipt,ensure_ascii=False,indent=2))
    if bad:raise SystemExit(1)
if __name__=="__main__":main()
