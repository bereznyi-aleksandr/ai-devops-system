#!/usr/bin/env python3
import json
from pathlib import Path

OUTBOX = Path("governance/telegram_outbox.jsonl")
TRANSPORT = Path("governance/transport/results.jsonl")
PICK = Path("governance/tmp/telegram_pick.json")

def load_jsonl(path):
    rows = []
    if not path.exists():
        return rows
    for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append((line_no, json.loads(line)))
        except Exception:
            pass
    return rows

def stable_hash(text):
    return "len_" + str(len(text))

def already_delivered(line_no, msg_hash):
    for _, rec in load_jsonl(TRANSPORT):
        if rec.get("record_type") == "telegram_delivery_result" and rec.get("outbox_line") == line_no and rec.get("message_hash") == msg_hash and rec.get("status") in ["sent", "sent_synthetic"]:
            return True
    return False

def priority(rec):
    cycle_id = str(rec.get("cycle_id", ""))
    msg = str(rec.get("message", ""))
    if cycle_id.startswith("bem548") or "BEM-548" in msg:
        return 100
    if rec.get("canonical") is True:
        return 50
    return 10

candidates = []
for line_no, rec in load_jsonl(OUTBOX):
    if rec.get("status") not in ["ready_to_send", "queued_for_sender", "queued"]:
        continue
    message = str(rec.get("message", "")).strip()
    if not message:
        continue
    msg_hash = stable_hash(message)
    if already_delivered(line_no, msg_hash):
        continue
    candidates.append([priority(rec), line_no, rec, msg_hash])

if candidates:
    candidates.sort()
    item = candidates[-1]
    rec = item[2]
    pick = {"found": True, "outbox_line": item[1], "cycle_id": rec.get("cycle_id", "telegram-outbox-live"), "message": str(rec.get("message", "")), "message_hash": item[3], "priority": item[0]}
else:
    pick = {"found": False}
PICK.parent.mkdir(parents=True, exist_ok=True)
PICK.write_text(json.dumps(pick, ensure_ascii=False), encoding="utf-8")
print(json.dumps(pick, ensure_ascii=False))
