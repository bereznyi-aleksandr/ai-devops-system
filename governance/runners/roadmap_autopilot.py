#!/usr/bin/env python3
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
Q=Path(__file__).resolve().parents[2]/"governance/roadmap/ACTIVE_QUEUE.json"
D={"DONE","DONE_LIMITED_SCOPE","DONE_STATIC_ONLY","DONE_PREPARED_FOR_EXTERNAL_AUDIT","SKIPPED_BY_OPERATOR"}
def n():return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def ready(t,m):
 for d in t.get("depends_on",[]) or []:
  i=d if isinstance(d,str) else d.get("id") if isinstance(d,dict) else None
  ok=D if isinstance(d,str) else {str(x).upper() for x in d.get("accepted_statuses",D)}
  if not i or str(m.get(i,{}).get("status","")).upper() not in ok:return False
 return True
def bind(t,i,tr):
 e=t.get("execution")
 if isinstance(e,dict):
  w=e.get("workflow_id"); x=e.get("inputs",{})
  if not isinstance(w,str) or not w or not isinstance(x,dict):raise ValueError("invalid_execution_binding")
  x={str(k):str(v).replace("${task_id}",i).replace("${trace_id}",tr) for k,v in x.items()}
 elif i=="BEM949-DSM-1":w="dsm1-lifecycle-probe.yml";x={"trace_id":tr,"task_id":i}
 else:w=i.lower()+".yml";x={}
 if w.startswith("/") or ".." in Path(w).parts:raise ValueError("invalid_workflow_id")
 x.setdefault("trace_id",tr);return w,x
def main(f):
 q=json.loads(Q.read_text()); ts=q.get("tasks",[])
 if not isinstance(ts,list):raise ValueError("queue_tasks_invalid")
 m={t["id"]:t for t in ts if isinstance(t,dict) and isinstance(t.get("id"),str)}
 c=q.get("current_task"); a=m.get(c)
 if a and str(a.get("status","")).upper()=="IN_PROGRESS":r={"action":"stop","reason":"active_task_in_progress","task_id":c,"queue_changed":False}
 else:
  t=m.get(f) if f else next((z for z in ts if isinstance(z,dict) and str(z.get("status","")).upper()=="PENDING" and ready(z,m)),None)
  if not t or str(t.get("status","")).upper()!="PENDING" or not ready(t,m):
   q["queue_state"]="BLOCKED" if any(str(z.get("status","")).upper().startswith("BLOCKED") for z in ts if isinstance(z,dict)) else "IDLE";q["updated_at"]=n();Q.write_text(json.dumps(q,ensure_ascii=False,indent=2)+"\n");r={"action":"stop","reason":"no_eligible_pending_task","queue_changed":True}
  else:
   i=t["id"];tr="autopilot_"+i.lower().replace("-","_")+"_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ");w,x=bind(t,i,tr);t.update({"status":"IN_PROGRESS","started_at":n(),"trace_id":tr});q.update({"current_task":i,"queue_state":"ACTIVE","updated_at":n()});Q.write_text(json.dumps(q,ensure_ascii=False,indent=2)+"\n");r={"action":"dispatch","task_id":i,"trace_id":tr,"workflow_id":w,"inputs":x,"queue_changed":True}
 return r
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--force-task-id",default="");p.add_argument("--output",required=True);a=p.parse_args();r=main(a.force_task_id.strip());Path(a.output).write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n");print(json.dumps(r,ensure_ascii=False,sort_keys=True))
