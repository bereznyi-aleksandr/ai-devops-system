#!/usr/bin/env python3
"""BEM-948 trace-scoped GitHub Actions dispatcher. HTTP 204 is dispatch only."""
import argparse,json,os,urllib.request,urllib.error,hashlib
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2]
P=R/"governance/state/dispatch_processed.jsonl"
E=R/"governance/state/dispatch_executed.jsonl"
C=R/"governance/config/provider_config.json"
O=R/"governance/proofs/BEM948_dispatch_executor_receipt.json"
def now(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def rows(p):
    out=[]
    if not p.exists(): return out
    for n,s in enumerate(p.read_text(encoding="utf-8",errors="replace").splitlines(),1):
        if not s.strip(): continue
        try: x=json.loads(s);out.append(x if isinstance(x,dict) else {"_invalid":"non_object","_line":n})
        except Exception as e: out.append({"_invalid":"json","_line":n,"_error":str(e)})
    return out
def key(x): return str(x.get("dispatch_id") or x.get("trace_id") or "")
def write(x):
    O.parent.mkdir(parents=True,exist_ok=True)
    O.write_text(json.dumps(x,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def stop(trace,reason,seen,skip):
    x={"status":"BLOCKED","protocol":"BEM-948","task_id":"BEM948-P0-REAL-DISPATCH-BRIDGE","created_at":now(),"trace_filter":trace,"processed_items_seen":seen,"dispatched_count":0,"failed_count":0,"skipped_count":skip,"dispatches":[],"checks":{"trace_id_required":True,"trace_scope_enforced":True,"historical_replay_prevented":True,"http_204_means_dispatched_not_completed":True,"sha_type_explicit":True},"blockers":[reason],"next_task":"BEM948-P0-AUTOREPAIR-DISPATCH-EXECUTOR"};write(x);return x
def post(tok,repo,api,w,inputs):
    q=urllib.request.Request(f"{api.rstrip('/')}/repos/{repo}/actions/workflows/{w}/dispatches",data=json.dumps({"ref":"main","inputs":inputs}).encode(),method="POST",headers={"Authorization":f"Bearer {tok}","Accept":"application/vnd.github+json","Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(q,timeout=30) as r:return r.status,r.read().decode(errors="replace")[:400]
    except urllib.error.HTTPError as e:return e.code,e.read().decode(errors="replace")[:400]
    except Exception as e:return None,str(e)[:400]
def main():
    a=argparse.ArgumentParser();a.add_argument("--trace-id",required=True);a.add_argument("--max",type=int,default=1);z=a.parse_args();t=z.trace_id.strip()
    if not t: raise SystemExit("trace_id_required")
    src=rows(P);done={key(x) for x in rows(E)};pick=[];skip=0
    for x in src:
        if x.get("_invalid") or x.get("status")!="processed" or x.get("dispatch_result")!="planned" or str(x.get("trace_id") or x.get("dispatch_id") or "")!=t or key(x) in done:skip+=1;continue
        pick.append(x)
        if len(pick)>=max(1,z.max):break
    if not pick:
        r=stop(t,"matching_planned_dispatch_absent",len(src),skip);print(json.dumps(r,ensure_ascii=False));raise SystemExit(1)
    try: providers=json.loads(C.read_text(encoding="utf-8")).get("providers",{})
    except Exception as e:
        r=stop(t,f"provider_config_unavailable:{e}",len(src),skip);print(json.dumps(r,ensure_ascii=False));raise SystemExit(1)
    tok=os.getenv("AI_SYSTEM_GITHUB_PAT") or os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or "";repo=os.getenv("GITHUB_REPOSITORY","");api=os.getenv("GITHUB_API_URL","https://api.github.com");out=[]
    for x in pick:
        payload=x.get("payload") if isinstance(x.get("payload"),dict) else {};provider=str(x.get("provider_selected") or x.get("provider") or "");workflow=str(x.get("requiret_workflow_id") or x.get("path_line") or "");role=str(x.get("logical_role") or x.get("role") or "curator");pc=providers.get(provider) if isinstance(providers,dict) else None
        r={"protocol":"BEM-948","task_id":"BEM948-P0-REAL-DISPATCH-BRIDGE","created_at":now(),"dispatch_id":key(x),"trace_id":t,"logical_role":role,"provider_selected":provider,"target_workflow_id":workflow,"source_processed_sha256":hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest(),"source_processed_sha256_type":"sha256_content","dispatch_result":"failed","http_status":None,"blocker":None}
        if not isinstance(pc,dict):r["blocker"]="provider_missing"
        elif pc.get("enabled") is not True:r["blocker"]="provider_disabled"
        elif pc.get("workflow_id")!=workflow:r["blocker"]="target_workflow_mismatch"
        elif not tok:r["blocker"]="github_token_missing"
        elif not repo:r["blocker"]="github_repository_missing"
        else:
            i={"role":role,"provider":"claude" if provider=="claude_code" else provider,"trace_id":t,"cycle_id":str(payload.get("cycle_id") or x.get("cycle_id") or f"dispatch_{t}"),"task_type":str(payload.get("task_type") or "default_development"),"task":str(payload.get("task") or f"Governance dispatch {t}")};r["inputs"]=i;s,b=post(tok,repo,api,workflow,i);r["http_status"]=s;r["response_excerpt"]=b
            if s==204:r["dispatch_result"]="dispatched"
            else:r["blocker"]=f"workflow_dispatch_http_{s if s is not None else 'network_error'}"
        out.append(r)
    E.parent.mkdir(parents=True,exist_ok=True)
    with E.open("a",encoding="utf-8") as f:
        for x in out:f.write(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n")
    bad=[x for x in out if x["dispatch_result"]!="dispatched"]
    receipt={"status":"PASS" if out and not bad else "BLOCKED","protocol":"BEM-948","task_id":"BEM948-P0-REAL-DISPATCH-BRIDGE","created_at":now(),"trace_filter":t,"processed_items_seen":len(src),"dispatched_count":sum(x["dispatch_result"]=="dispatched" for x in out),"failed_count":len(bad),"skipped_count":skip,"dispatches":out,"checks":{"trace_id_required":True,"trace_scope_enforced":True,"historical_replay_prevented":True,"http_dispatch_attempted":bool(out),"http_204_means_dispatched_not_completed":True,"sha_type_explicit":True},"blockers":[x["blocker"] for x in bad if x.get("blocker")],"next_task":"BEM948-P0-LIVE-OBJECT-E2E" if out and not bad else "BEM948-P0-AUTOREPAIR-DISPATCH-EXECUTOR"};write(receipt);print(json.dumps(receipt,ensure_ascii=False,indent=2))
    if receipt["status"]!="PASS":raise SystemExit(1)
if __name__=="__main__":main()
