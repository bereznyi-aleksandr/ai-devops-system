#!/usr/bin/env python3
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
SEP="\n"
KYIV=timezone(timedelta(hours=3))
STATE=Path("governance/state/claude_code_action_smoke_state.json")
REPORT=Path("governance/reports/claude_code_action_smoke_state.md")
mode=sys.argv[1] if len(sys.argv)>1 else "unknown"
outcome=sys.argv[2] if len(sys.argv)>2 else "unknown"
now=datetime.now(KYIV).strftime("%Y-%m-%d | %H:%M (UTC+3)")
try:
    data=json.loads(STATE.read_text(encoding="utf-8", errors="ignore")) if STATE.exists() else {}
except Exception:
    data={}
runs=data.get("runs",[]) if isinstance(data.get("runs"),list) else []
runs.append({"time":now,"mode":mode,"outcome":outcome})
data.update({"schema_version":"claude_code_action_smoke_state.v1","status":mode,"last_outcome":outcome,"updated_at":now,"runs":runs[-50:],"operator_role":"none"})
STATE.parent.mkdir(parents=True,exist_ok=True)
STATE.write_text(json.dumps(data,indent=2,ensure_ascii=False)+SEP,encoding="utf-8")
REPORT.parent.mkdir(parents=True,exist_ok=True)
REPORT.write_text("# Claude Code Action Smoke State"+SEP+SEP+"Status: "+mode+SEP+"Outcome: "+outcome+SEP+"Updated: "+now+SEP+"Operator role: none"+SEP,encoding="utf-8")
print(json.dumps({"status":mode,"outcome":outcome,"updated_at":now},ensure_ascii=False))
