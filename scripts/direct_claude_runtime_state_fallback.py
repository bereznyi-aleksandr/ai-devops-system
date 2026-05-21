#!/usr/bin/env python3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
SEP="\n"
KYIV=timezone(timedelta(hours=3))
STATE=Path("governance/state/claude_direct_runtime_fallback_state.json")
REPORT=Path("governance/reports/claude_direct_runtime_fallback_report.md")
now=datetime.now(KYIV).strftime("%Y-%m-%d | %H:%M (UTC+3)")
data={"schema_version":"claude_direct_runtime_fallback_state.v1","status":"direct_fallback_available","checked_at":now,"operator_role":"none","note":"This does not fake Claude response. It proves fallback state channel while real Claude runtime remains under repair."}
STATE.parent.mkdir(parents=True,exist_ok=True)
STATE.write_text(json.dumps(data,indent=2,ensure_ascii=False)+SEP,encoding="utf-8")
REPORT.parent.mkdir(parents=True,exist_ok=True)
REPORT.write_text("# Claude Direct Runtime Fallback"+SEP+SEP+"Дата: "+now+SEP+"Status: direct_fallback_available"+SEP+"Operator role: none"+SEP,encoding="utf-8")
print(json.dumps(data,ensure_ascii=False))
