#!/usr/bin/env python3
import argparse,json,re
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; CFG=ROOT/'governance/config/provider_config.json'; PROOFS=ROOT/'governance/proofs'; STATE=ROOT/'governance/state/provider_failover_decisions.jsonl'
def now(): return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def safe(x): return re.sub(r'[^A-Za-z0-9_.:-]+','_',str(x or 'trace'))[:120]
def decide(req):
    c=json.loads(CFG.read_text(encoding='utf-8')); role=req.get('role') or 'curator'; reason=req.get('failure_reason')
    roles=c.get('roles',{}); providers=c.get('providers',{})
    if role not in roles: raise RuntimeError('role_missing:'+role)
    primary=roles[role].get('primary'); fallback=roles[role].get('fallback')
    def ok(pid):
        p=providers.get(pid,{})
        return bool(p.get('enabled')) and not p.get('deprecated') and (role in p.get('role_support',[]) or '*' in p.get('role_support',[]))
    use_fb=reason in set(c.get('fallback_on',[])) and ok(fallback)
    selected=fallback if use_fb else primary
    blocker=None if ok(selected) else 'no_available_provider'
    p=providers.get(selected,{})
    return {'status':'PASS' if not blocker else 'BLOCKED','protocol':'BEM-935','task_id':'BEM935-P1-PROVIDER-FAILOVER','created_at':now(),'trace_id':safe(req.get('trace_id')),'role':role,'failure_reason':reason,'primary_provider':primary,'fallback_provider':fallback,'provider_selected':selected,'target_workflow_id':p.get('workflow_id'),'decision_mode':'fallback' if use_fb else 'primary','fallback_used':use_fb,'decision_source':'governance/runners/provider_failover.py','blocker':blocker,'non_claim':'routing decision only; no downstream LLM success claimed'}
def write(d):
    PROOFS.mkdir(parents=True,exist_ok=True); STATE.parent.mkdir(parents=True,exist_ok=True)
    p=PROOFS/(f"BEM935_provider_failover_{safe(d['trace_id'])}.json"); p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with STATE.open('a',encoding='utf-8') as f: f.write(json.dumps(d,ensure_ascii=False,sort_keys=True)+'\n')
    return p
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--role',default='curator'); ap.add_argument('--trace-id'); ap.add_argument('--failure-reason'); ap.add_argument('--write-proof',action='store_true'); a=ap.parse_args()
    d=decide({'role':a.role,'trace_id':a.trace_id,'failure_reason':a.failure_reason})
    if a.write_proof: d['proof_path']=str(write(d).relative_to(ROOT))
    print(json.dumps(d,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
