#!/usr/bin/env python3
import json
from pathlib import Path
INBOX=Path("governance/audit_mailbox/gpt_to_claude")
STATE=Path("governance/state/claude_inbound_seen_items.json")
try:
    data=json.loads(STATE.read_text(encoding="utf-8", errors="ignore")) if STATE.exists() else {}
except:
    data={}
seen=set(data.get("seen",[]))
files=sorted([p for p in INBOX.glob("*") if p.is_file()], key=lambda p: p.stat().st_mtime) if INBOX.exists() else []
latest=str(files[-1]) if files else ""
should="true" if latest and latest not in seen else "false"
print("should_run="+should)
print("latest_file="+latest)
