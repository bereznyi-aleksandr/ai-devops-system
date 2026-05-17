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
    total = 0
    for ch in text:
        total = (total * 131 + ord(ch)) % 1000000007
    return "len_" + str(len(text)) + "_sum_" + str(total)

def already_delivered(line_no, msg_hash):
    for _, rec in load_jsonl(TRANSPORT):
        if rec.get("record_type") == "telegram_delivery_result" and rec.get("outbox_line") == line_no and rec.get("message_hash") == msg_hash and rec.get("status") in ["sent", "sent_synthetic"]:
            return True
    return False

pick = {"found": False}
for line_no, rec in load_jsonl(OUTBOX):
    if rec.get("status") not in ["queued_for_sender", "queued"]:
        continue
    message = str(rec.get("message", "")).strip()
    if not message:
        continue
    msg_hash = stable_hash(message)
    if already_delivered(line_no, msg_hash):
        continue
    pick = {"found": True, "outbox_line": line_no, "cycle_id": rec.get("cycle_id", "telegram-outbox-live"), "message": message, "message_hash": msg_hash}
    break
PICK.parent.mkdir(parents=True, exist_ok=True)
PICK.write_text(json.dumps(pick, ensure_ascii=False), encoding="utf-8")
print(json.dumps(pick, ensure_ascii=False))
