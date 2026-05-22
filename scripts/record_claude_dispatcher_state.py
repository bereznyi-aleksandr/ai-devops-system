#!/usr/bin/env python3
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
SEP="\n"
KYIV=timezone(timedelta(hours=3))
mode=sys.argv[1] if len(sys.argv)>1 else "unknown"
outcome=sys.argv[2] if len(sys.argv)>2 else mode
now=datetime.now(KYIV).strftime("%Y-%m-%d | %H:%M (UTC+3)")
state_path=Path("governance/state/claude_inbound_mailbox_workflow_state.json")
try:
    data=json.loads(state_path.read_text(encoding="utf-8", errors="ignore")) if state_path.exists() else {}
except Exception:
    data={}
runs=data.get("runs",[]) if isinstance(data.get("runs",[]),list) else []
runs.append({"time":now,"mode":mode,"outcome":outcome})
data.update({"schema_version":"claude_inbound_mailbox_workflow_state.v1","status":"runtime_"+mode,"latest":{"mode":mode,"outcome":outcome,"time":now},"started_at":data.get("started_at") or now,"completed_at":now if mode=="complete" else data.get("completed_at"),"claude_action_outcome":outcome if mode=="complete" else data.get("claude_action_outcome"),"runs":runs[-200:],"operator_role":"none"})
state_path.parent.mkdir(parents=True,exist_ok=True)
state_path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+SEP,encoding="utf-8")
print(json.dumps({"status":data["status"],"mode":mode,"outcome":outcome,"time":now},ensure_ascii=False))
