#!/usr/bin/env python3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
SEP="\n"
KYIV=timezone(timedelta(hours=3))
now=datetime.now(KYIV).strftime("%Y-%m-%d | %H:%M (UTC+3)")
mail=Path("governance/audit_mailbox/claude_to_gpt")
state=Path("governance/state/real_claude_response_verification_state.json")
real=[]
blockers=[]
if mail.exists():
    for p in sorted(mail.glob("*")):
        if not p.is_file():
            continue
        txt=p.read_text(encoding="utf-8", errors="ignore")
        up=txt.upper()
        low=(p.name+" "+txt).lower()
        bad="NOT CLAUDE APPROVAL" in up or "RUNTIME BLOCKER" in up or "not treat this as claude" in low
        ok=("CLAUDE RESPONSE" in up and "DECISION:" in up and ("APPROVED" in up or "CHANGE_REQUIRED" in up or "BLOCKED" in up))
        item={"path":str(p),"size":len(txt)}
        if bad:
            blockers.append(item)
        elif ok:
            real.append(item)
data={"schema_version":"real_claude_response_verification_state.v1","status":"real_response_found" if real else "real_response_missing","checked_at":now,"real_responses":real[-20:],"blocker_files":blockers[-20:],"operator_role":"none"}
state.parent.mkdir(parents=True,exist_ok=True)
state.write_text(json.dumps(data,indent=2,ensure_ascii=False)+SEP,encoding="utf-8")
print(json.dumps(data,ensure_ascii=False))
if not real:
    raise SystemExit(2)
