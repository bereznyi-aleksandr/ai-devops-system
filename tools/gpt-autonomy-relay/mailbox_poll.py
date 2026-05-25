#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
RESPONSE = ROOT / "governance/audit/mailbox/from_claude/BEM859_PROTOCOL_ALIGNMENT_RESPONSE.md"
RESULT = ROOT / "governance/runtime/mailbox_polling/BEM859_PROTOCOL_ALIGNMENT_RESULT.md"
LAST = ROOT / "governance/runtime/mailbox_polling/BEM859_LAST_CHECK.md"
EVENTS = ROOT / "governance/events/bem859_mailbox_poll.jsonl"
FINAL = ["APPROVED", "APPROVED_WITH_AMENDMENTS", "BLOCKED_WITH_REASON"]

def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def event(obj):
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    obj["timestamp"] = obj.get("timestamp") or now()
    with EVENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def find_status(text):
    for status in FINAL:
        if status in text:
            return status
    return None

def main():
    ts = now()
    text = RESPONSE.read_text(encoding="utf-8") if RESPONSE.exists() else ""
    status = find_status(text)
    if status:
        RESULT.parent.mkdir(parents=True, exist_ok=True)
        RESULT.write_text(f"# BEM-859 protocol alignment result\nStatus: {status}\nChecked: {ts}\nSource: {RESPONSE}\n", encoding="utf-8")
        event({"event": "BEM859_MAILBOX_FINAL_STATUS", "status": status, "source": str(RESPONSE)})
        print("BEM859_MAILBOX_FINAL_STATUS | " + status)
        return 0
    LAST.parent.mkdir(parents=True, exist_ok=True)
    LAST.write_text(f"# BEM-859 mailbox last check\nStatus: WAITING_FOR_CLAUDE_RESPONSE\nChecked: {ts}\nSource: {RESPONSE}\nInterval: 60 seconds\n", encoding="utf-8")
    event({"event": "BEM859_MAILBOX_WAITING", "source": str(RESPONSE)})
    print("BEM859_MAILBOX_WAITING")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
