#!/usr/bin/env python3
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
R=Path(__file__).resolve().parents[2]; W=R/'.github/workflows'; O=R/'governance/proofs/BEM949_p1_static_validation_receipt.json'
def now(): return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def sha(b): return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def main():
 try: import yaml
 except ImportError:
  x={'schema_version':1,'task_id':'BEM949-P1-ALT-UNBLOCK','created_at':now(),'status':'BLOCKED','outcome':'static_validation_unavailable','blocker':'PyYAML unavailable'}
  O.parent.mkdir(parents=True,exist_ok=True);O.write_text(json.dumps(x,indent=2)+'\n');print(json.dumps({'task_status':'BLOCKED','receipt_path':str(O.relative_to(R))}));return 1
 checks=[];problems=[];files=sorted(W.glob('bem949-p1-*.yml'))
 for p in files:
  raw=p.read_bytes()
  try:
   d=yaml.safe_load(raw.decode())
   if not isinstance(d,dict): raise ValueError('top_level_not_mapping')
   if d.get('on',d.get(True)) is None: raise ValueError('missing_on')
   jobs=d.get('jobs')
   if not isinstance(jobs,dict) or not jobs: raise ValueError('missing_or_empty_jobs')
   if any(not isinstance(v,dict) or ('runs-on' not in v and 'uses' not in v) for v in jobs.values()): raise ValueError('invalid_job')
   checks.append({'path':str(p.relative_to(R)),'git_blob_sha':sha(raw),'sha_type':'git_blob','yaml_safe_load':'PASS','static_schema':'PASS'})
  except Exception as e: problems.append({'path':str(p.relative_to(R)),'error':type(e).__name__+':'+str(e)})
 if not files: problems.append({'path':'.github/workflows/bem949-p1-*.yml','error':'no_matching_workflows'})
 ok=not problems;x={'schema_version':1,'task_id':'BEM949-P1-ALT-UNBLOCK','created_at':now(),'status':'PASS' if ok else 'BLOCKED','outcome':'static_pass_only' if ok else 'blocked_with_detail','evidence_kind':'yaml_safe_load_static_validation','scope':'.github/workflows/bem949-p1-*.yml','checks':checks,'problems':problems,'limitations':['Static validation does not prove GitHub Actions dispatch or run-level success.','BEM949-P1-CI-STABILIZE remains independently blocked until run-level evidence exists.'],'broad_release_pass_claimed':False}
 O.parent.mkdir(parents=True,exist_ok=True);O.write_text(json.dumps(x,indent=2)+'\n');print(json.dumps({'task_status':'DONE_STATIC_ONLY' if ok else 'BLOCKED','receipt_path':str(O.relative_to(R))}));return 0 if ok else 1
raise SystemExit(main())
