#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
R=Path(__file__).resolve().parents[2]
Q=R/"governance/roadmap/ACTIVE_QUEUE.json"
O=R/"governance/proofs/BEM949_dsm1_rearm_receipt.json"
def now():return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
q=json.loads(Q.read_text());t=next(x for x in q["tasks"] if x.get("id")=="BEM949-DSM-1")
stamp=now();old=str(t.get("trace_id",""))
changed=t.get("status")=="IN_PROGRESS"
if changed:
 t.update({"status":"AWAITING_GENUINE_RECEIPT","rearmed_at":stamp,"stale_trace_id":old,"stale_reason":"terminal_receipt_absent_for_active_trace"})
 q.update({"current_task":None,"queue_state":"READY","updated_at":stamp,"version":int(q.get("version",0))+1})
 Q.write_text(json.dumps(q,ensure_ascii=False,indent=2)+"\n")
O.parent.mkdir(parents=True,exist_ok=True)
O.write_text(json.dumps({"schema_version":1,"protocol":"BEM-949","task_id":"BEM949-DSM-1","created_at":stamp,"status":"REAREMED" if changed else "NO_CHANGE","runtime_execution_claim":False,"prior_trace_id":old,"reason":"stale IN_PROGRESS state had no matching terminal receipt; rearmed for genuine workflow attempt"},ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"changed":changed,"prior_trace_id":old}))
