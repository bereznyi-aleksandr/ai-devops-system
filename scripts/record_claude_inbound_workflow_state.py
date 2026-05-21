#!/usr/bin/env python3
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
SEP="\n"
KYIV=timezone(timedelta(hours=3))
STATE=Path("governance/state/claude_inbound_mailbox_workflow_state.json")
REPORT=Path("governance/reports/claude_inbound_mailbox_workflow_state.md")
mode=sys.argv[1] if len(sys.argv)>1 else "tick"
outcome=sys.argv[2] if len(sys.argv)>2 else "unknown"
now=datetime.now(KYIV).strftime("%Y-%m-%d | %H:%M (UTC+3)")
try:
    data=json.loads(STATE.read_text(encoding="utf-8", errors="ignore")) if STATE.exists() else {}
except:
    data={}
runs=data.get("runs",[]) if isinstance(data.get("runs",[]),list) else []
runs.append({"time":now,"mode":mode,"outcome":outcome})
runs=runs[-100:]
if mode=="start": data["started_at"]=now
if mode=="complete":
    data["completed_at"]=now
    data["claude_action_outcome"]=outcome
data.update({"schema_version":"claude_inbound_mailbox_workflow_state.v1","status":"runtime_"+mode,"latest":{"mode":mode,"outcome":outcome,"time":now},"runs":runs,"operator_role":"none"})
STATE.parent.mkdir(parents=True,exist_ok=True)
STATE.write_text(json.dumps(data,indent=2,ensure_ascii=False)+SEP,encoding="utf-8")
REPORT.parent.mkdir(parents=True,exist_ok=True)
REPORT.write_text("# Claude Inbound Mailbox Workflow State"+SEP+SEP+"Time: "+now+SEP+"Mode: "+mode+SEP+"Outcome: "+outcome+SEP+"Operator role: none"+SEP,encoding="utf-8")
print(json.dumps({"mode":mode,"outcome":outcome,"time":now},ensure_ascii=False))
