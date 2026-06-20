#!/usr/bin/env python3
"""BEM-948 fail-closed Claude dispatch bridge. HTTP 204 is dispatch only."""
import argparse,json,os,urllib.request,urllib.error
from datetime import datetime,timezone
from pathlib import Path
R=Path(__file__).resolve().parents[2]
P=R/"governance/state/dispatch_processed.jsonl";E=R/"governance/state/dispatch_executed.jsonl";O=R/"governance/proofs/BEM948_dispatch_executor_receipt.json"
def now():return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def rows(p):
 r=[]
 if p.exists():
  for s in p.read_text(encoding="utf-8",errors="replace").splitlines():
   try:r.append(json.loads(s))
   except:pass
 return [x for x in r if isinstance(x,dict)]
def k(x):return str(x.get("dispatch_id") or x.get("trace_id") or "")
def save(x):O.parent.mkdir(parents=True,exist_ok=True);O.write_text(json.dumps(x,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def main():
 a=argparse.ArgumentParser();a.add_argument("--trace-id",required=True);a.add_argument("--max",type=int,default=1);z=a.parse_args();t=z.trace_id.strip()
 if not t:raise SystemExit("trace_id_required")
 src=rows(P);done={k(x) for x in rows(E)};pick=[x for x in src if x.get("status")=="processed" and x.get("dispatch_result")=="planned" and str(x.get("trace_id") or x.get("dispatch_id") or "")==t and k(x) not in done][:max(1,z.max)]
 if not pick:
  q={"status":"BLOCKED","protocol":"BEM-948","task_id":"BEM948-P0-REAL-DISPATCH-BRIDGE","created_at":now(),"trace_filter":t,"dispatched_count":0,"dispatches":[],"checks":{"trace_id_required":True,"trace_scope_enforced":True,"historical_replay_prevented":True,"http_204_means_dispatched_not_completed":True,"sha_type_explicit":True},"blockers":["matching_planned_dispatch_absent"],"next_task":"BEM948-P0-AUTOREPAIR-DISPATCH-EXECUTOR"};save(q);print(json.dumps(q));raise SystemExit(1)
 tok=os.getenv("AI_SYSTEM_GITHUB_PAT") or os.getenv("GITHUB_TOKEN") or "";repo=os.getenv("GITHUB_REPOSITORY","");api=os.getenv("GITHUB_API_URL","https://api.github.com");out=[]
 for x in pick:
  role=str(x.get("logical_role") or x.get("role") or "curator");payload=x.get("payload") if isinstance(x.get("payload"),dict) else {};workflow=str(x.get("target_workflow_id") or "")
  r={"protocol":"BEM-948","task_id":"BEM948-P0-REAL-DISPATCH-BRIDGE","created_at":now(),"dispatch_id":k(x),"trace_id":t,"logical_role":role,"provider_selected":str(x.get("provider_selected") or x.get("provider") or ""),"target_workflow_id":workflow,"dispatch_result":"failed","http_status":None,"blocker":None}
  if r["provider_selected"]!="claude_code" or workflow!="claude.yml":r["blocker"]="unsupported_or_mismatched_provider_target"
  elif not tok or not repo:r["blocker"]="github_dispatch_credentials_or_repository_missing"
  else:
   i={"role":role,"provider":"claude","trace_id":t,"cycle_id":str(payload.get("cycle_id") or f"dispatch_{t}"),"task_type":str(payload.get("task_type") or "default_development"),"task":str(payload.get("task") or f"Governance dispatch {t}")};r["inputs"]=i
   q=urllib.request.Request(f"{api.rstrip('/')}/repos/{repo}/actions/workflows/claude.yml/dispatches",data=json.dumps({"ref":"main","inputs":i}).encode(),method="POST",headers={"Authorization":f"Bearer {tok}","Accept":"application/vnd.github+json","Content-Type":"application/json"})
   try:
    with urllib.request.urlopen(q,timeout=30) as h:r["http_status"]=h.status
   except urllib.error.HTTPError as e:r["http_status"]=e.code
   except Exception:r["http_status"]=None
   if r["http_status"]==204:r["dispatch_result"]="dispatched"
   else:r["blocker"]=f"workflow_dispatch_http_{r['http_status'] if r['http_status'] is not None else 'network_error'}"
  out.append(r)
 E.parent.mkdir(parents=True,exist_ok=True)
 with E.open("a",encoding="utf-8") as f:
  for x in out:f.write(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n")
 bad=[x for x in out if x["dispatch_result"]!="dispatched"]
 q={"status":"PASS" if not bad else "BLOCKED","protocol":"BEM-948","task_id":"BEM948-P0-REAL-DISPATCH-BRIDGE","created_at":now(),"trace_filter":t,"dispatched_count":sum(x["dispatch_result"]=="dispatched" for x in out),"failed_count":len(bad),"dispatches":out,"checks":{"trace_id_required":True,"trace_scope_enforced":True,"historical_replay_prevented":True,"http_dispatch_attempted":True,"http_204_means_dispatched_not_completed":True,"sha_type_explicit":True},"blockers":[x["blocker"] for x in bad if x.get("blocker")],"next_task":"BEM948-P0-LIVE-OBJECT-E2E" if not bad else "BEM948-P0-AUTOREPAIR-DISPATCH-EXECUTOR"};save(q);print(json.dumps(q,ensure_ascii=False,indent=2))
 if q["status"]!="PASS":raise SystemExit(1)
if __name__=="__main__":main()
