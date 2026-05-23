#!/usr/bin/env python3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
SEP="\n"
KYIV=timezone(timedelta(hours=3))
OUT=Path("governance/audit_mailbox/claude_to_gpt")
STATE=Path("governance/state/claude_response_guard_state.json")
now=datetime.now(KYIV).strftime("%Y-%m-%d | %H:%M (UTC+3)")
OUT.mkdir(parents=True,exist_ok=True)
real=[]
for p in sorted(OUT.glob("*")):
    if p.is_file():
        txt=p.read_text(encoding="utf-8", errors="ignore")
        up=txt.upper(); low=(p.name+" "+txt).lower()
        bad="NOT CLAUDE APPROVAL" in up or "RUNTIME BLOCKER" in up or "not treat this as claude" in low
        ok="DECISION:" in up and ("APPROVED" in up or "CHANGE_REQUIRED" in up or "BLOCKED" in up) and ("CLAUDE RESPONSE" in up or "Claude Internal Auditor" in txt)
        if ok and not bad:
            real.append(str(p))
if real:
    status="real_response_present"
else:
    status="real_response_missing_after_claude_step"
    fail=OUT/("bem845_claude_response_missing_failure.md")
    fail.write_text("# BEM-845 | CLAUDE RESPONSE MISSING | NOT CLAUDE APPROVAL"+SEP+SEP+"Дата: "+now+SEP+"Decision: BLOCKED"+SEP+"Reason: Claude dispatcher ran or was dispatched, but no real Claude response file was detected."+SEP+"Required fix: inspect Claude action/provider outcome and prompt/output path."+SEP,encoding="utf-8")
STATE.parent.mkdir(parents=True,exist_ok=True)
STATE.write_text(json.dumps({"schema_version":"claude_response_guard_state.v1","status":status,"real_responses":real,"checked_at":now},indent=2,ensure_ascii=False)+SEP,encoding="utf-8")
print(json.dumps({"status":status,"real_responses":real},ensure_ascii=False))
