#!/usr/bin/env python3
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
SEP="\n"
KYIV=timezone(timedelta(hours=3))
STATE=Path("governance/state/claude_inbound_seen_items.json")
latest=sys.argv[1] if len(sys.argv)>1 else ""
outcome=sys.argv[2] if len(sys.argv)>2 else "unknown"
try:
    data=json.loads(STATE.read_text(encoding="utf-8", errors="ignore")) if STATE.exists() else {}
except:
    data={}
seen=data.get("seen",[]) if isinstance(data.get("seen",[]),list) else []
if latest and outcome=="success" and latest not in seen:
    seen.append(latest)
now=datetime.now(KYIV).strftime("%Y-%m-%d | %H:%M (UTC+3)")
data.update({"schema_version":"claude_inbound_seen_items.v1","seen":seen,"last_file":latest,"last_outcome":outcome,"updated_at":now})
STATE.parent.mkdir(parents=True,exist_ok=True)
STATE.write_text(json.dumps(data,indent=2,ensure_ascii=False)+SEP,encoding="utf-8")
print(json.dumps({"latest":latest,"outcome":outcome,"seen_count":len(seen)},ensure_ascii=False))
