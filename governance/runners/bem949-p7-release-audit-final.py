#!/usr/bin/env python3
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
R=Path(__file__).resolve().parents[2];Q=R/'governance/roadmap/ACTIVE_QUEUE.json';O=R/'governance/proofs/BEM949_p7_audit_package.json';L=R/'governance/logs/execution_log.jsonl'
def now():return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def sha(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
 qb=Q.read_bytes();q=read(Q);inv=[];limits=[]
 for t in q.get('tasks',[]):
  if not isinstance(t,dict) or not isinstance(t.get('id'),str) or not t['id'].startswith('BEM949-'):continue
  r={'id':t['id'],'status':t.get('status'),'receipt':t.get('receipt')};ref=t.get('receipt')
  if isinstance(ref,str) and (R/ref).is_file():
   p=R/ref;r['receipt_sha']=sha(p.read_bytes())
   try:x=read(p);r['receipt_status']=x.get('status');r['receipt_outcome']=x.get('outcome')
   except Exception as e:r['receipt_error']=type(e).__name__
  inv.append(r);s=str(t.get('status','')).upper()
  if s not in {'DONE','DONE_LIMITED_SCOPE','DONE_STATIC_ONLY','SKIPPED_BY_OPERATOR'}:limits.append({'task_id':t['id'],'status':s or 'MISSING'})
 x={'schema_version':1,'task_id':'BEM949-P7-RELEASE-AUDIT-FINAL','created_at':now(),'status':'PASS','outcome':'audit_package_prepared','evidence_kind':'external_audit_package','queue_blob_sha':sha(qb),'queue_sha_type':'git_blob','task_inventory':inv,'limitations':limits,'external_auditor_required':True,'audit_disposition':'AWAITING_EXTERNAL_CLAUDE_AUDIT','broad_release_pass_claimed':False}
 O.parent.mkdir(parents=True,exist_ok=True);O.write_text(json.dumps(x,indent=2)+'\n')
 L.parent.mkdir(parents=True,exist_ok=True)
 with L.open('a') as h:h.write(json.dumps({'timestamp':now(),'task_id':'BEM949-P7-RELEASE-AUDIT-FINAL','status':'prepared','receipt':str(O.relative_to(R)),'notification':'P7 audit package ready; external Claude auditor required.'},sort_keys=True)+'\n')
 print(json.dumps({'task_status':'DONE_PREPARED_FOR_EXTERNAL_AUDIT','receipt_path':str(O.relative_to(R))}))
raise SystemExit(main())
