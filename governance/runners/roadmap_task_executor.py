#!/usr/bin/env python3
"""Generic declared-task executor with convention runners; no ID allowlist."""
import argparse, hashlib, json, re, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
QUEUE=ROOT/"governance/roadmap/ACTIVE_QUEUE.json"
LOG=ROOT/"governance/logs/execution_log.jsonl"
PROOFS=ROOT/"governance/proofs"
PASS={"PASS","DONE"}
BLOCK={"BLOCKED","FAIL","FAILED","ERROR"}

def now(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def dump(x): return (json.dumps(x,ensure_ascii=False,indent=2)+"\n").encode()
def blob(b): return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
def load(p):
 x=json.loads(p.read_text(encoding="utf-8"))
 if not isinstance(x,dict): raise ValueError(f"JSON object required: {p}")
 return x
def safe(ref):
 p=(ROOT/ref).resolve()
 try: rel=p.relative_to(ROOT)
 except ValueError: raise ValueError(f"path outside repository: {ref}")
 return p,str(rel)
def slug(x): return re.sub(r"[^A-Za-z0-9_.-]+","_",x).strip("_").lower()
def runner_json(out):
 for line in reversed(out.splitlines()):
  try:
   x=json.loads(line)
   if isinstance(x,dict): return x
  except json.JSONDecodeError: pass
 return {}
def receipt_ok(ref):
 p,rel=safe(ref)
 if not p.is_file(): return False,rel,"missing_task_receipt"
 try: status=str(load(p).get("status","")).upper()
 except Exception: return False,rel,"unreadable_task_receipt"
 if status in PASS:return True,rel,None
 if status in BLOCK:return False,rel,f"receipt_status_{status.lower()}"
 return False,rel,"receipt_status_not_pass"
def execute(task,tid):
 exe=task.get("execution")
 inferred=False
 if exe is None:
  candidate=f"governance/runners/{slug(tid)}.py"; p,_=safe(candidate)
  if p.is_file(): exe={"kind":"python","entrypoint":candidate,"args":[],"timeout_seconds":900}; inferred=True
 if not isinstance(exe,dict): return "BLOCKED",{"error":"missing_execution_binding"},None
 if str(exe.get("kind","python")).lower()!="python": return "BLOCKED",{"error":"unsupported_execution_kind"},None
 entry=exe.get("entrypoint")
 if not isinstance(entry,str) or not entry:return "BLOCKED",{"error":"python_execution_requires_entrypoint"},None
 p,rel=safe(entry)
 if not p.is_file() or p.suffix!=".py":return "BLOCKED",{"error":"missing_python_entrypoint","entrypoint":entry},None
 args=exe.get("args",[])
 if not isinstance(args,list) or not all(isinstance(x,(str,int,float)) for x in args):return "BLOCKED",{"error":"invalid_python_args"},None
 try: timeout=max(1,min(int(exe.get("timeout_seconds",900)),3600))
 except Exception:return "BLOCKED",{"error":"invalid_timeout_seconds"},None
 try:
  source=p.read_text(encoding="utf-8"); compile(source,str(p),"exec")
  run=subprocess.run([sys.executable,str(p),*map(str,args)],cwd=ROOT,capture_output=True,text=True,timeout=timeout)
 except subprocess.TimeoutExpired as e:return "BLOCKED",{"error":"python_execution_timeout","entrypoint":rel,"stdout_tail":(e.stdout or "")[-4000:],"stderr_tail":(e.stderr or "")[-4000:]},None
 result=runner_json(run.stdout)
 detail={"entrypoint":rel,"returncode":run.returncode,"stdout_tail":run.stdout[-4000:],"stderr_tail":run.stderr[-4000:],"runner_result":result,"execution_inferred_from_task_id":inferred}
 ref=result.get("receipt_path") if isinstance(result.get("receipt_path"),str) else exe.get("receipt_path")
 if run.returncode!=0:return "BLOCKED",detail,ref if isinstance(ref,str) else None
 status=str(result.get("task_status","DONE")).upper()
 if not re.fullmatch(r"[A-Z][A-Z0-9_]*",status) or status in {"PENDING","IN_PROGRESS"}:return "BLOCKED",{**detail,"error":"invalid_runner_task_status"},None
 if not isinstance(ref,str) or not ref:return "BLOCKED",{**detail,"error":"runner_did_not_provide_receipt_path"},None
 ok,relref,err=receipt_ok(ref); detail["receipt"=relref
 if not ok:return "BLOCKED",{**detail,"error":err},relref
 return status,detail,relref
def main(tid,trace):
 q=load(QUEUE); tasks=q.get("tasks")
 if not isinstance(tasks,list):raise ValueError("ACTIVE_QUEUE.tasks must be a list")
 t=next((x for x in tasks if isinstance(x,dict) and x.get("id")==tid),None)
 if t is None:raise ValueError(f"unknown task: {tid}")
 if str(t.get("status","")).upper()!="IN_PROGRESS":raise ValueError(f"task is not IN_PROGRESS: {tid}")
 status,detail,ref=execute(t,tid)
 rec={"schema_version":1,"task_id":tid,"trace_id":trace,"created_at":now(),"status":"PASS" if status!="BLOCKED" else "BLOCKED","task_status":status,"evidence_kind":"runtime_task_executor","execution":detail,"task_receipt":ref}
 ep=PROOFS/f"{slug(tid)}_executor_receipt.json"; ep.parent.mkdir(parents=True,exist_ok=True); b=dump(rec);ep.write_bytes(b)
 t.update(status=status,completed_at=now(),executor_receipt=str(ep.relative_to(ROOT)),executor_receipt_sha=blob(b),executor_receipt_sha_type="git_blob")
 if ref:
  p,rr=safe(ref)
  if p.is_file():t.update(receipt=rr,receipt_sha=blob(p.read_bytes()),receipt_sha_type="git_blob")
 if status=="BLOCKED":t["blocker"]=str(detail.get("error","task_execution_blocked"))
 else:t.pop("blocker",None)
 if q.get("current_task")==tid:q["current_task"]=None
 q.update(queue_state="PENDING" if status!="BLOCKED" else "BLOCKED",updated_at=now());QUEUE.write_bytes(dump(q))
 LOG.parent.mkdir(parents=True,exist_ok=True)
 with LOG.open("a",encoding="utf-8") as h:h.write(json.dump({"timestamp":now(),"task_id":tid,"trace_id":trace,"status":status.lower(),"receipt":t.get("receipt","source":"roadmap_task_executor"},sort_keys=True)+"\n")
 print(json.dumps(rec,ensure_ascii=False,sort_keys=True))
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--task-id",required=True);p.add_argument("--trace-id",required=True);a=p.parse_args();main(a.task_id,a.trace_id)
