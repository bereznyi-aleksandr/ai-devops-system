#!/usr/bin/env python3
"""Queue-driven roadmap selector; workflow bindings live in ACTIVE_QUEUE."""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
QUEUE=ROOT/"governance/roadmap/ACTIVE_QUEUE.json"
DONE={"DONE","DONE_LIMITED_SCOPE","DONE_STATIC_ONLY","DONE_PREPARED_FOR_EXTERNAL_AUDIT","SKIPPED_BY_OPERATOR"}
def now():return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def ok(task,byid):
    for dep in task.get("depends_on",[]) or []:
        if isinstance(dep,str):did=dep;allowed=DONE
        elif isinstance(dep,dict):did=dep.get("id");allowed={str(x).upper() for x in dep.get("accepted_statuses",DONE)}
        else:return False
        if not isinstance(did,str) or str((byid.get(did)or{}).get("status","")).upper() not in allowed:return False
    return True
def binding(task,tid,trace):
    e=task.get("execution")
    if isinstance(e,dict):
        if str(e.get("kind","workflow")).lower()!="workflow":raise ValueError("unsupported_execution_kind")
        wf=e.get("workflow_id");raw=e.get("inputs",{})
        if not isinstance(wf,str) or not wf or not isinstance(raw,dict):raise ValueError("invalid_workflow_binding")
        inp={str(k):str(v).replace("${task_id}",tid).replace("${trace_id}",trace) for k,v in raw.items()}
    elif tid=="BEM949-DSM-1":
        wf="dsm1-lifecycle-probe.yml";inp={"trace_id":trace,"task_id":tid}
    else:
        wf=tid.lower()+".yml";inp={}
    if wf.startswith("/") or ".." in Path(wf).parts:raise ValueError("invalid_workflow_id")
    inp.setdefault("trace_id",trace)
    return wf,inp
def main(force):
    q=json.loads(QUEUE.read_text(encoding="utf-8"));tasks=q.get("tasks")
    if not isinstance(tasks,list):raise ValueError