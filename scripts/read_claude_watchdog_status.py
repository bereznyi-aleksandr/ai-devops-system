#!/usr/bin/env python3
import json
from pathlib import Path
p=Path("governance/state/claude_mailbox_minute_watchdog_state.json")
print(json.loads(p.read_text()).get("status","missing") if p.exists() else "missing")
