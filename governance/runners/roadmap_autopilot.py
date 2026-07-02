#!/usr/bin/env python3
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
Q=Path(__file__).resolve().parents[2]/"governance/roadmap/ACTIVE_QUEUE.json"
D={"DONE","DONE_LIMITED_SCOPE","DONE_STATIC_ONLY","DONE_PREPARED_FOR_EXTERNAL_AUDIT","SKIPPED_BY_OPERATOR"}
T="BEM949-DSM-1"
def n():return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def ready(t,m):
 for d in t.get("depends_on",[]) or []:
  i=d if isinstance(d,str) else d.get("id") if isinstance(d,dict) else None
  a=D if isinstance(d,str) else {str(x).upper() for x in d.get("accepted_statuses",D)}
  if not i or str(m.get(i,{}).get("status","")).upper() not in a:return False
 return True
def main(force):
 q=json.loads(Q.read_text());ts=q.get("tasks",[])
 if not isinstance(ts,list):raise ValueError("queue_tasks_invalid")
 m={t["id"]:t for t in ts if isinstance(t,dict) and isinstance(t.get("id"),str)}
 c=q.get("current_task");active=m.get(c)
 if active and str(active.get("status","")).upper()=="IN_PROGRESS":
  return {"action":"stop","reason":"active_task_in_progress","task_id":c,"queue_changed":False}
 if force and force!=T:raise ValueError("dsm1_autopilot_accepts_only_BEM949_DSM_1")
 t=m.get(T)
 if not t or str(t.get("status","")).upper()!="PENDING" or not ready(t,m):
  return {"action":"stop","reason":"dsm1_not_eligible","task_id":T,"queue_changed":False}
 tr="autopilot_bem949_dsm_1_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
 t.update({"status":"IN_PROGRESS","started_at":n(),"trace_id":tr})
 q.update({"current_task":T,"queue_state":"ACTIVE","updated_at":n()})
 Q.write_text(json.dumps(q,ensure_ascii=False,indent=2)+"\n")
 return {"action":"dispatch","task_id":T,"trace_id":tr,"workflow_id":"dsm1-lifecycle-probe.yml","inputs":{"trace_id":tr,"task_id":T},"queue_changed":True}
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--force-task-id",default="");p.add_argument("--output",required=True);a=p.parse_args();r=main(a.force_task_id.strip());Path(a.output).write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n");print(json.dumps(r,ensure_ascii=False,sort_keys=True))
