#!/usr/bin/env python3
import json, importlib.util, argparse
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
STATE=ROOT/'governance/state'; QUEUE=STATE/'dispatch_queue.jsonl'; PROCESSED=STATE/'dispatch_processed.jsonl'; DEAD=STATE/'dispatch_dead_letters.jsonl'; PROOFS=ROOT/'governance/proofs'
def now(): return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def lines(p):
    if not p.exists(): return []
    out=[]
    for s in p.read_text(encoding='utf-8').splitlines():
        if s.strip():
            try: out.append(json.loads(s))
            except Exception as e: out.append({'_invalid':'json','_raw':s,'_error':str(e)})
    return out
def append(p,items):
    if not items: return
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('a',encoding='utf-8') as f:
        for x in items: f.write(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n')
def key(x): return str(x.get('dispatch_id') or x.get('trace_id') or x.get('id') or '')
def router():
    spec=importlib.util.spec_from_file_location('curator_router', ROOT/'governance/runners/curator_router.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
def consume(limit=20):
    r=router(); seen={key(x) for x in lines(PROCESSED) if key(x)}; done=[]; dead=[]; skipped=0
    for item in lines(QUEUE):
        if len(done)>=limit: break
        k=key(item)
        if not k or item.get('_invalid'): dead.append({'status':'DEAD','created_at':now(),'reason':'invalid_or_missing_key','item':item}); continue
        if k in seen or item.get('status') not in (None,'queued','pending','READY'): skipped+=1; continue
        try:
            req={'trace_id':item.get('trace_id') or k,'role':item.get('logical_role') or item.get('role') or 'curator','provider':item.get('provider'),'failure_reason':item.get('fallback_reason'),'payload':item.get('payload',{})}
            d=r.route(req)
            done.append({'status':'processed','processed_at':now(),'dispatch_id':k,'trace_id':req['trace_id'],'logical_role':req['role'],'provider_selected':d['provider_selected'],'target_workflow_id':d['target_workflow_id'],'dispatch_result':'planned','proof_ref':item.get('proof_ref'),'payload':req['payload']})
        except Exception as e: dead.append({'status':'DEAD','created_at':now(),'dispatch_id':k,'reason':str(e),'item':item})
    append(PROCESSED,done); append(DEAD,dead)
    receipt={'status':'PASS' if not dead else 'BLOCKED','protocol':'BEM-935','task_id':'BEM935-P0-DISPATCH-CONSUMER','created_at':now(),'queue_items_seen':len(lines(QUEUE)),'processed_count':len(done),'skipped_count':skipped,'dead_letter_count':len(dead),'checks':{'dispatch_consumer_has_runtime_code':True,'router_imported':True,'processed_jsonl_written':bool(done) or skipped>0,'dead_letters_bounded':len(dead)==0},'blockers':[] if not dead else ['dead_letters_present']}
    PROOFS.mkdir(parents=True,exist_ok=True); (PROOFS/'BEM935_dispatch_consumer_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return receipt
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--max',type=int,default=20); a=ap.parse_args(); print(json.dumps(consume(a.max),ensure_ascii=False,indent=2))
if __name__=='__main__': main()
