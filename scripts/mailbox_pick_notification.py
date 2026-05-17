#!/usr/bin/env python3
import json
from pathlib import Path

NL = "\n"
MAILBOX_DIRS = [Path("governance/audit_mailbox/claude_to_gpt"), Path("governance/audit_mailbox/gpt_to_claude")]
STATE_PATH = Path("governance/state/mailbox_dispatcher_state.json")
TMP_DIR = Path("governance/tmp")
PICK_PATH = TMP_DIR / "mailbox_pick.json"
MSG_PATH = TMP_DIR / "mailbox_message.txt"

def load_state():
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

state = load_state()
processed = set(state.get("processed_files", []))
candidates = []
for folder in MAILBOX_DIRS:
    if folder.exists():
        for item in sorted(folder.glob("*.md"), key=lambda p: str(p)):
            if item.is_file():
                candidates.append(item)

picked = None
for item in candidates:
    if str(item) not in processed:
        picked = item
        break

TMP_DIR.mkdir(parents=True, exist_ok=True)
if picked is None:
    pick = {"picked": False, "notify_operator": False, "message": "", "mailbox_file": None, "reason": "no_new_mailbox_file"}
else:
    pick = {"picked": True, "notify_operator": False, "message": "", "mailbox_file": str(picked), "reason": "routine_mailbox_no_telegram_use_decision_queue"}

MSG_PATH.write_text("", encoding="utf-8")
PICK_PATH.write_text(json.dumps(pick, ensure_ascii=False, indent=2) + NL, encoding="utf-8")
print(json.dumps(pick, ensure_ascii=False))
