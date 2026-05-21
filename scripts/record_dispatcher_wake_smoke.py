#!/usr/bin/env python3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
SEP="\n"
KYIV=timezone(timedelta(hours=3))
STATE=Path("governance/state/dispatcher_wake_smoke_state.json")
REPORT=Path("governance/reports/dispatcher_wake_smoke_state.md")
now=datetime.now(KYIV).strftime("%Y-%m-%d | %H:%M (UTC+3)")
try:
    data=json.loads(STATE.read_text(encoding="utf-8", errors="ignore")) if STATE.exists() else {}
except:
    data={}
runs=data.get("runs",[]) if isinstance(data.get("runs",[]),list) else []
runs.append({"time":now,"mode":"wake_smoke"})
data.update({"schema_version":"dispatcher_wake_smoke_state.v1","status":"wake_smoke_seen","last_seen_at":now,"runs":runs[-100:],"operator_role":"none"})
STATE.parent.mkdir(parents=True,exist_ok=True)
STATE.write_text(json.dumps(data,indent=2,ensure_ascii=False)+SEP,encoding="utf-8")
REPORT.parent.mkdir(parents=True,exist_ok=True)
REPORT.write_text("# Dispatcher Wake Smoke State"+SEP+SEP+"Status: wake_smoke_seen"+SEP+"Last seen: "+now+SEP+"Operator role: none"+SEP,encoding="utf-8")
print(json.dumps({"status":"wake_smoke_seen","last_seen_at":now},ensure_ascii=False))
