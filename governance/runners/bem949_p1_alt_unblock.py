#!/usr/bin/env python3
"""Static YAML evidence only; it never replaces P1 run-level evidence."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
WF=ROOT/".github/workflows"
OUT=ROOT/"governance/proofs/BEM949_p1_static_validation_receipt.json"
def now():return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def blob(b):return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
def write(x):
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(x,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def main():
 try:import yaml
 except ImportError:
  write({"schema_version":1,"task_id":"BEM949-P1-ALT-UNBLOCK","created_at":now(),"status":"BLOCKED","outcome":"static_validation_unavailable","blocker":"pyyaml_not_available","p1_run_level_evidence_replaced":False})
  print(json.dumps({"task_status":"BLOCKED","receipt_path":str(OUT.relative_to(ROOT))}));return 1
 files=sorted(WF.glob("bem949-p1-*.yml")); results=[]; errors=[]
 if not files:errors.append({"error":"no_matching_bem949_p1_workflows"})
 for p in files:
  b=p.read_bytes();e={"path":str(p.relative_to(ROOT)),"sha":blob(b),"sha_type":"git_blob"}
  try:
   d=yaml.safe_load(b.decode("utf-8"))
   if not isinstance(d,dict):raise ValueError("workflow root must be a mapping")
   if not isinstance(d.get("name"),str) or not d["name"].strip():raise ValueError("workflow name missing")
   if d.get("on",d.get(True)) is None:raise ValueError("workflow trigger missing")
   if not isinstance(d.get("jobs"),dict) or not d["jobs"]:raise ValueError("workflow requires at least one job")
   e.update(yaml_safe_load="PASS",job_count=len(d["jobs"]))
  except Exception as x:
   e.update(yaml_safe_load="BLOCKED",error=f"{type(x).__name__}: {x}");errors.append(e.copy())
  results.append(e)
 rec={"schema_version":1,"task_id":"BEM949-P1-ALT-UNBLOCK","created_at":now(),"status":"PASS" if not errors else "BLOCKED","outcome":"static_pass_only" if not errors else "static_validation_blocked","evidence_kind":"yaml.safe_load structural validation","files":results,"errors":errors,"limitations":["Static YAML validation does not provide GitHub Actions run-level outcome or log evidence.","BEM949-P1-CI-STABILIZE remains BLOCKED_OPERATOR_DECISION until run-level evidence is recorded.","No Broad Release PASS is implied."],"p1_run_level_evidence_replaced":False}
 write(rec);print(json.dumps({"task_status":"DONE_STATIC_ONLY" if not errors else "BLOCKED","receipt_path":str(OUT.relative_to(ROOT))},ensure_ascii=False));return 0 if not errors else 1
if __name__=="__main__":raise SystemExit(main())
