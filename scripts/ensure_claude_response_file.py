#!/usr/bin/env python3
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
SEP="\n"
KYIV=timezone(timedelta(hours=3))
outcome=sys.argv[1] if len(sys.argv)>1 else "unknown"
resp=Path("governance/audit_mailbox/claude_to_gpt/bem844_claude_response.md")
now=datetime.now(KYIV).strftime("%Y-%m-%d | %H:%M (UTC+3)")
if resp.exists() and "CLAUDE RESPONSE | BEM-844" in resp.read_text(encoding="utf-8", errors="ignore"):
    print(json.dumps({"status":"real_response_exists","path":str(resp)},ensure_ascii=False))
else:
    resp.parent.mkdir(parents=True,exist_ok=True)
    resp.write_text("# CLAUDE RESPONSE | BEM-844"+SEP+SEP+"Date: "+now+SEP+"Decision: BLOCKED"+SEP+"Reason: Claude action did not produce the required response file. Outcome="+outcome+SEP+"This is a fail-closed runtime result from the Claude dispatcher workflow, not an architecture approval."+SEP,encoding="utf-8")
    print(json.dumps({"status":"fail_closed_response_written","path":str(resp),"outcome":outcome},ensure_ascii=False))
