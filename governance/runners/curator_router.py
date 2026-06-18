#!/usr/bin/env python3
import json, argparse, re
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CFG=ROOT/'governance/config/provider_config.json'
PROOFS=ROOT/'governance/proofs'
def now(): return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def safe(x): return re.sub(r'[^A-Za-z0-9_.:-]+','_',str(x or 'route'))[:120]
def load(): return json.loads(CFG.read_text(encoding='utf-8'))
def route(req):
    cfg=load(); role=req.get('role') or req.get('logical_role') or 'curator'
    roles=cfg.get('roles',{}); providers=cfg.get('providers',{})
    if role not in roles: raise SystemExit('role_missing:'+role)
    pid=req.get('provider') or req.get('provider_id') or roles[role].get('primary')
    if req.get('failure_reason') in cfg.get('fallback_on',[]) and roles[role].get('fallback'):
        pid=roles[role]['fallback']
    p=providers.get(pid) or {}
    if not p.get('enabled') or p.get('deprecated'):
        raise SystemExit('provider_disabled_or_deprecated:'+str(pid))
    if role not in p.get('role_support',[]) and '*' not in p.get('role_support',[]):
        raise SystemExit('provider_role_unsupported:'+str(pid)+':'+role)
    workflow=p.get('workflow_id')
    if not workflow: raise SystemExit('provider_workflow_missing:'+str(pid))
    return {'status':'PASS','router':'governance/runners/curator_router.py','created_at':now(),'trace_id':safe(req.get('trace_id')),'role':role,'provider_selected':pid,'target_workflow_id':workflow,'dispatch_result':'planned','decision_source':'python_runtime_router','ttl_seconds':cfg.get('ttl_seconds',1800),'stale_ignore':True,'fallback_used':pid==roles[role].get('fallback'),'blocker':None}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--role',default='curator'); ap.add_argument('--trace-id'); ap.add_argument('--provider'); ap.add_argument('--failure-reason'); ap.add_argument('--write-proof',action='store_true')
    a=ap.parse_args(); req={'role':a.role,'trace_id':a.trace_id,'provider':a.provider,'failure_reason':a.failure_reason}
    d=route(req)
    if a.write_proof:
        PROOFS.mkdir(parents=True,exist_ok=True); path=PROOFS/(f"provider_router_{safe(d['trace_id'])}.json"); path.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); d['proof_path']=str(path.relative_to(ROOT))
    print(json.dumps(d,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
