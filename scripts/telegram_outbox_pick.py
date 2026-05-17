#!/usr/bin/env python3
import json
from pathlib import Path

OUTBOX = Path("governance/telegram_outbox.jsonl")
TRANSPORT = Path("governance/transport/results.jsonl")
PICK = Path("governance/tmp/telegram_pick.json")
CURRENT = Path("governance/state/operator_progress_current.json")

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

def delivered(line_no, msg_hash):
    for _, rec in load_jsonl(TRANSPORT):
        if rec.get("record_type") == "telegram_delivery_result" and rec.get("outbox_line") == line_no and rec.get("message_hash") == msg_hash and rec.get("status") in ["sent", "sent_synthetic"]:
            return True
    return False

def current_bem():
    if not CURRENT.exists():
        return ""
    try:
        return str(json.loads(CURRENT.read_text(encoding="utf-8")).get("bem", ""))
    except Exception:
        return ""

def priority(rec):
    cycle = str(rec.get("cycle_id", ""))
    msg = str(rec.get("message", ""))
    bem = current_bem()
    score = 0
    if rec.get("priority") == "operator_progress":
        score += 1000
    if bem and bem in msg:
        score += 500
    if cycle.startswith("bem550") or "BEM-550" in msg:
        score += 400
    if rec.get("status") == "ready_to_send":
        score += 100
    if "BEM-540" in msg or "synthetic" in msg.lower():
        score -= 300
    if rec.get("canonical") is True:
        score += 10
    return score

candidates = []
for line_no, rec in load_jsonl(OUTBOX):
    if rec.get("status") not in ["ready_to_send", "queued_for_sender", "queued"]:
        continue
    message = str(rec.get("message", "")).strip()
    if not message:
        continue
    msg_hash = stable_hash(message)
    if delivered(line_no, msg_hash):
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
