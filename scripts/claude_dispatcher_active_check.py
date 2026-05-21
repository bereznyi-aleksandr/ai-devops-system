#!/usr/bin/env python3
import json
import os
from pathlib import Path
active_file=Path("governance/autonomy/claude_mailbox_watchdog_active.json")
active=False
if active_file.exists():
    try:
        active=json.loads(active_file.read_text(encoding="utf-8", errors="ignore")).get("active") is True
    except:
        active=False
out=Path(os.environ.get("GITHUB_OUTPUT", "governance/tmp/claude_dispatcher_output.env"))
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("a", encoding="utf-8") as h:
    h.write("active="+("true" if active else "false")+"\n")
print("active="+("true" if active else "false"))
