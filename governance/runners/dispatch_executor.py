#!/usr/bin/env python3
"""BEM-948 trace-scoped dispatcher. HTTP 204 means dispatched, never completed."""
import argparse,json,os,urllib.request,urllib.error,hashlib
from datetime import datetime,timezone
from pathlib import Path
R=Path(__file__).resolve().parents[2]
P=R/"governance/state/dispatch_processed.jsonl";E=R/"governance/state/dispatch_executed.jsonl";C=R/"governance/config/provider_config.json";O=R/"governance/proofs/BEM948_dispatch_executor_receipt.json"
def now():return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def read(p):
 out=[]
 if p.exists():
  for n,s in enumerate(p.read_text(encoding="utf-8",errors="replace").splitlines(),1):
   if s.strip():
    try:
     x=json.loads(s);out.append(x if isinstance(x,dict) else {"_invalid":"non_object","_line":n})
    except Exception as e:out.append({"_invalid":"json","_line":n,"_error":str(e)})
 return out
def kid(x):return str(x.get("dispatch_id") or x.get("trace_id") or "")
def put(x):
 O.parent.mkdir(parents=True,exist_ok=True);O.write_text(json.dumps(x,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def base(t,status,seen,skipped,items,blockers):
 return {"status":status,"protocol":"BEM-948","task_id":"BEM948-P0-REAL-DISPATCH-BRIDGE","created_at":now(),"trace_filter":t,"processed_items_seen":seen,"dispatched_count":sum(y.get("dispatch_result")=="dispatched" for y in items),"failed_count":sum(y.get("dispatch_result")!="dispatched" for y in items),"skipped_count":skipped,"dispatches":items,"checks":{"trace_id_required":True,"trace_scope_enforced":True,"historical_replay_prevented":True,"http_204_means_dispatched_not_completed":True,"sha_type_explicit":True},"blockers":blockers,"next_task":"BEM948-P0-LIVE-OBJECT-E2E" if status=="PASS" else "BEM948-P0-AUTOREPAIR-DISPATCH-EXECUTOR"}
def post(tok,repo,api,w,i):
 q=urllib.request.Request(f"{api.rstrip('/')}/repos/{repo}/actions/workflows/{w}/dispatches",data=json.dumps({"ref":"main","inputs":i}).encode(),method="POST",headers={"Authorization":f"Bearer {tok}","Accept":"application/vnd.github+json","Content-Type":"application/json"})
 try:
  with urllib.request.urlopen(q,timeout=30) as r:return r.status,r.read().decode(errors="replace")[:400]
 except urllib.error.HTTPError as e:return e.code,e.read().decode(errors="replace")[:400]
 except Exception as e:return None,str(e)[:400]
def main():
 a=argparse.ArgumentParser();a.add_argument("--trace-id",required=True);a.add_argument("--max",type=int,default=1);z=a.parse_args();t=z.trace_id.strip()
 if not t:raise SystemExit("trace_id_required")
 src=read(P);done={kid(y) for y in read(E)};chosen=[];skip=0
 for x in src:
  if x.get("_invalid") or x.get("status")!="processed" or x.get("dispatch_result")!="planned" or str(x.get("trace_id") or x.get("dispatch_id") or "")!=t or kid(x) in done:skip+=1;continue
  chosen.append(x)
  if len(chosen)>=max(1,z.max):break
 if not chosen:
  r=base(t,"BLOCKED",len(src),skip,[],["matching_planned_dispatch_absent"]);put(r);print(json.dumps(r,ensure_ascii=False));raise SystemExit(1)
 try:providers=json.loads(C.read_text(encoding="utf-8")).get("providers",{})
 except Exception as e:
  r=base(t,"BLOCKED",len(src),skip,[],[f"provider_config_unavailable:{e}"]);put(r);print(json.dumps(r,ensure_ascii=False));raise SystemExit(1)
 tok=os.getenv("AI_SYSTEM_GITHUB_PAT") or os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or "";repo=os.getenv("GITHUB_REPOSITORY","");api=os.getenv("GITHUB_API_URL","https://api.github.com");out=[]
 for x in chosen:
  payload=x.get("payload") if isinstance(x.get("payload"),dict) else {};provider=str(x.get("provider_selected") or x.get("provider") or "");workflow=str(x.get("path_line") or "");role=str(x.get("logical_role") or x.get("role") or "curator");pc=providers.get(provider) if isinstance(providers,dict) else None
  r={"protocol":"BEM-948","task_id":"BEM948-P0-REAL-DISPATCH-BRIDGE","created_at":now(),"dispatch_id":kid(x),"trace_id":t,"logical_role":role,"provider_selected":provider,"target_workflow_id":workflow,"source_processed_sha256":hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest(),"source_processed_sha256_type":"sha256_content","dispatch_result":"failed","http_status":None,"blocker":None}
  if not isinstance(pc,dict):r["blocker"]="provider_missing"
  elif pc.get("enabled") is not True:r["blocker"]="provider_disabled"
  elif pc.get("workflow_id")!=workflow:r["blocker"]="target_workflow_mismatch"
  elif not tok:r["blocker"]="github_token_missing"
  elif not repo:r["blocker"]="github_repository_missing"
  else:
   i={"role":role,"provider":"claude" if provider=="claude_code" else provider,"trace_id":t,"cycle_id":str(payload.get("cycle_id") or x.get("cycle_id") or f"dispatch_{t}"),"task_type":str(payload.get("task_type") or "default_development"),"task":str(payload.get("task") or f"Governance dispatch {trace}")};r["inputs"]=inputs
            code,body=call(tok,repo,api,workflow,inputs);r["http_status"]=code;r["response_excerpt"]=body
            if code==204:r["dispatch_result"]="dispatched"
            else:r["blocker"]=f"workflow_dispatch_http_{code if code is not None else 'network_error'}"
        out.append(r)
    E.parent.mkdir(parents=True,exist_ok=True)
    with E.open("a",encoding="utf-8") as f:
        for x in out:f.write(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n")
    bad=[x for x in out if x["dispatch_result"]!="dispatched"];r=base(trace,"PASS" if not bad else "BLOCKED",len(sorce),skipped,out,[x["blocker"] for x in bad if x.get("blocker")]);put(r);print(json.dumps(r,ensure_ascii=False,indent=2))
    if r["status"]!="PASS":raise SystemExit(1)
if __name__=="__main__":main()
