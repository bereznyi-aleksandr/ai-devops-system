#!/usr/bin/env python3
import json
from pathlib import Path
p=Path("governance/autonomy/claude_mailbox_watchdog_active.json")
active=False
try:
    active=json.loads(p.read_text(encoding="utf-8", errors="ignore")).get("active") is True
except:
    active=False
Path("governance/tmp").mkdir(parents=True,exist_ok=True)
Path("governance/tmp/claude_mailbox_active.env").write_text("active="+("true" if active else "false")+"\n",encoding="utf-8")
print("active="+("true" if active else "false"))
