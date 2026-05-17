#!/usr/bin/env python3
import json
from pathlib import Path
OUTBOX=Path("governance/telegram_outbox.jsonl")
TRANSPORT=Path("governance/transport/results.jsonl")
STATE=Path("governance/state/contour_status.json")
msg="BEM-HOURLY | 2026-05-17 | hourly curator report alive | progress feed active | blocker=null"
rec={"record_type":"telegram_hourly_report","cycle_id":"curator-hourly-report","delivery_mode":"curator-hourly-report.yml","canonical":True,"status":"ready_to_send","message":msg,"created_at":"workflow_runtime","blocker":None,"priority":"operator_progress"}
OUTBOX.parent.mkdir(parents=True,exist_ok=True)
with OUTBOX.open("a",encoding="utf-8") as f: f.write(json.dumps(rec,ensure_ascii=False)+"\n")
TR=rec.copy(); TR["record_type"]="curator_hourly_report_generated"; TR["artifact_path"]="governance/telegram_outbox.jsonl"; TR["commit_sha"]=None
TRANSPORT.parent.mkdir(parents=True,exist_ok=True)
with TRANSPORT.open("a",encoding="utf-8") as f: f.write(json.dumps(TR,ensure_ascii=False)+"\n")
state={}
if STATE.exists():
    try: state=json.loads(STATE.read_text(encoding="utf-8"))
    except Exception: state={}
state["curator_hourly_report_last_generated"]={"status":"ready_to_send","message":msg,"updated_at":"workflow_runtime"}
STATE.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
print(msg)
