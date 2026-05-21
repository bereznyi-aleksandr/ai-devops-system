#!/usr/bin/env python3
import json
from pathlib import Path
active=Path("governance/autonomy/claude_mailbox_watchdog_active.json")
value=False
if active.exists():
    try:
        value=json.loads(active.read_text(encoding="utf-8", errors="ignore")).get("active") is True
    except:
        value=False
print("active="+("true" if value else "false"))
