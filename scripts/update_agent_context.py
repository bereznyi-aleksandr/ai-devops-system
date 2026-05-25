#!/usr/bin/env python3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
SEP="\n"
KYIV=timezone(timedelta(hours=3))
now=datetime.now(KYIV).strftime("%Y-%m-%d | %H:%M (UTC+3)")
state_dir=Path("governance/state")
latest=[]
if state_dir.exists():
    latest=sorted([p for p in state_dir.glob("bem*.json") if p.is_file()], key=lambda p: p.stat().st_mtime)[-10:]
blockers=[]
for p in latest:
    try:
        data=json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        continue
    b=data.get("blocker")
    if b:
        blockers.append({"file":str(p),"blocker":b})
ctx=Path("governance/AGENT_CONTEXT.md")
text="# AGENT CONTEXT | CANONICAL START STATE"+SEP+SEP
text+="Updated: "+now+SEP+SEP
text+="## Purpose"+SEP+"Canonical startup context for GPT and Claude agents. Read before development action."+SEP+SEP
text+="## Current phase"+SEP+"Autonomous multi-agent development contour repair."+SEP+SEP
text+="## Required proof triad"+SEP+"1. workflow_dispatch_results status for Claude dispatcher."+SEP+"2. claude_inbound_mailbox_workflow_state runtime start or completion."+SEP+"3. real Claude response in governance/audit_mailbox/claude_to_gpt that is not NOT CLAUDE APPROVAL and not runtime blocker."+SEP+SEP
text+="## Latest BEM state files"+SEP
for p in latest:
    text+="- `"+str(p)+"`"+SEP
text+=SEP+"## Active blockers"+SEP
if blockers:
    for b in blockers[-5:]:
        text+="- `"+b["file"]+"`: "+json.dumps(b["blocker"],ensure_ascii=False)+SEP
else:
    text+="- Verify latest proof triad; no blocker extracted from latest state files."+SEP
text+=SEP+"## Operator decisions"+SEP+"1. Reports do not stop development."+SEP+"2. Operator is not mailbox relay."+SEP+"3. PASS requires evidence."+SEP+"4. Bad queue JSON must not kill runner."+SEP+"5. New agents read this file first."+SEP+SEP
text+="## Next action"+SEP+"Verify proof triad and repair the first missing proof. No issue comments."+SEP
ctx.write_text(text,encoding="utf-8")
Path("governance/state/agent_context.json").write_text(json.dumps({"schema_version":"agent_context.v1","updated_at":now,"latest_bem_state_files":[str(p) for p in latest],"blockers":blockers[-10:]},indent=2,ensure_ascii=False)+SEP,encoding="utf-8")
print("AGENT_CONTEXT updated at "+now)
