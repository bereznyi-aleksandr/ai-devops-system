#!/usr/bin/env python3
import importlib.util,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; PROOFS=ROOT/'governance/proofs'; LOG=ROOT/'governance/logs/execution_log.jsonl'
def now(): return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def mod():
    p=ROOT/'governance/runners/provider_failover.py'; s=importlib.util.spec_from_file_location('provider_failover',p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
def main():
    m=mod()
    a=m.decide({'role':'executor','trace_id':'bem935_primary','failure_reason':None})
    b=m.decide({'role':'executor','trace_id':'bem935_rate_limit','failure_reason':'rate_limit'})
    c=m.decide({'role':'executor','trace_id':'bem935_syntax','failure_reason':'syntax_error'})
    checks={'runtime_code_present':True,'primary_keeps_claude':a['provider_selected']=='claude_code','fallback_uses_cloud':b['fallback_used'] and b['provider_selected']=='gpt_codex_cloud','unrecognized_no_fallback':not c['fallback_used'] and c['provider_selected']=='claude_code','not_self_hosted':b['provider_selected']!='gpt_codex','no_blockers':all(x.get('blocker') is None for x in (a,b,c))}
    blockers=[k for k,v in checks.items() if not v]
    r={'status':'PASS' if not blockers else 'BLOCKED','protocol':'BEM-935','task_id':'BEM935-P1-PROVIDER-FAILOVER','created_at':now(),'stage':{'tasks_done':1,'tasks_total':3,'percent':33},'checks':checks,'decisions':{'primary':a,'fallback':b,'unrecognized':c},'blockers':blockers,'next_task':'BEM935-P1-TELEGRAM-INPUT-HANDLER' if not blockers else None}
    PROOFS.mkdir(parents=True,exist_ok=True); p=PROOFS/'BEM935_provider_failover_receipt.json'; p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    LOG.parent.mkdir(parents=True,exist_ok=True); LOG.open('a',encoding='utf-8').write(json.dumps({'timestamp':now(),'task_id':r['task_id'],'status':r['status'],'receipt':str(p.relative_to(ROOT))},ensure_ascii=False)+'\n')
    if blockers: raise SystemExit(','.join(blockers))
    print(json.dumps(r,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
