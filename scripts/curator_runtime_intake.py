#!/usr/bin/env python3
import json, os
from pathlib import Path
TRANSPORT=Path("governance/transport/results.jsonl")
STATE=Path("governance/state/role_cycle_state.json")
VALID_SOURCES=["gpt","claude","telegram"]
VALID_TYPES=["development","audit","hotfix"]
def load_rows():
    rows=[]
    if TRANSPORT.exists():
        for line in TRANSPORT.read_text(encoding="utf-8",errors="ignore").splitlines():
            if line.strip():
                try: rows.append(json.loads(line))
                except Exception: pass
    return rows
def append(rec):
    TRANSPORT.parent.mkdir(parents=True,exist_ok=True)
    with TRANSPORT.open("a",encoding="utf-8") as f: f.write(json.dumps(rec,ensure_ascii=False)+"\n")
trace=os.environ.get("TRACE_ID","")
task={"trace_id":trace,"source":os.environ.get("SOURCE","gpt"),"task_type":os.environ.get("TASK_TYPE","development"),"title":os.environ.get("TITLE",""),"objective":os.environ.get("OBJECTIVE",""),"created_at":os.environ.get("BEM_TIMESTAMP","workflow_runtime"),"blocker":None}
errors=[]
for key in ["trace_id","source","task_type","title","objective"]:
    if not str(task.get(key,"")).strip(): errors.append("missing_"+key)
if task["source"] not in VALID_SOURCES: errors.append("invalid_source")
if task["task_type"] not in VALID_TYPES: errors.append("invalid_task_type")
if trace and trace in [r.get("trace_id") for r in load_rows() if r.get("trace_id")]: errors.append("duplicate_trace_id")
accepted=not errors
blocker=None if accepted else {"code":"CURATOR_INTAKE_INVALID","errors":errors}
cycle=trace or "curator-intake-invalid"
validation={"record_type":"curator_intake_validation","cycle_id":cycle,"trace_id":trace,"source":"curator-runtime","status":"accepted" if accepted else "rejected","task":task,"artifact_path":"governance/transport/results.jsonl","commit_sha":None,"blocker":blocker,"created_at":task["created_at"]}
append(validation)
if accepted:
    append({"record_type":"curator_assignment","cycle_id":cycle,"trace_id":trace,"source":"curator-runtime","from_role":"curator","to_role":"role_orchestrator","status":"completed","decision":"submit_to_orchestrator","reason":"runtime_intake_validated","artifact_path":"governance/transport/results.jsonl","commit_sha":None,"blocker":None,"created_at":task["created_at"]})
st={}
if STATE.exists():
    try: st=json.loads(STATE.read_text(encoding="utf-8"))
    except Exception: st={}
st.update({"cycle_id":cycle,"curator_status":"ASSIGNED" if accepted else "BLOCKED","active_role":"curator","next_role":"role_orchestrator" if accepted else None,"last_curator_runtime_intake":validation,"blocker":blocker})
STATE.write_text(json.dumps(st,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
print(json.dumps(validation,ensure_ascii=False))
