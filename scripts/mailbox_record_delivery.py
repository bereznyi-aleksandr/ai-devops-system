#!/usr/bin/env python3
import json
from pathlib import Path
STATE_PATH = Path("governance/state/mailbox_dispatcher_state.json")
PICK_PATH = Path("governance/tmp/mailbox_pick.json")
STATUS_PATH = Path("governance/tmp/mailbox_telegram_status.txt")
OUTBOX_PATH = Path("governance/telegram_outbox.jsonl")
TRANSPORT_PATH = Path("governance/transport/results.jsonl")
REPORT_PATH = Path("governance/reports/bem569_mailbox_dispatcher_direct_telegram_result.md")

def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default

def append_jsonl(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "
")

state = load_json(STATE_PATH, {})
pick = load_json(PICK_PATH, {"picked": False, "message": "", "mailbox_file": None})
status = STATUS_PATH.read_text(encoding="utf-8", errors="ignore").strip() if STATUS_PATH.exists() else "not_sent_no_status"
blocker = None if status == "sent" or not pick.get("picked") else {"code": "MAILBOX_TELEGRAM_SEND_NOT_SENT", "status": status}
if pick.get("picked"):
    rec = {
        "record_type": "telegram_mailbox_notification",
        "cycle_id": "bem569-mailbox-dispatcher-direct-telegram",
        "delivery_mode": "mailbox-dispatcher-direct",
        "canonical": True,
        "status": "sent" if status == "sent" else "ready_to_send",
        "direct_send_status": status,
        "message": pick.get("message", ""),
        "mailbox_file": pick.get("mailbox_file"),
        "created_at": "workflow_runtime",
        "blocker": blocker,
        "priority": "mailbox_notification",
    }
    append_jsonl(OUTBOX_PATH, rec)
    tr = dict(rec)
    tr["record_type"] = "mailbox_direct_telegram_dispatch"
    append_jsonl(TRANSPORT_PATH, tr)
    if status == "sent":
        seen = set(state.get("sent_files", []))
        seen.add(pick.get("mailbox_file"))
        state["sent_files"] = sorted(seen)
state["last_run"] = {"picked": pick.get("picked"), "mailbox_file": pick.get("mailbox_file"), "status": status, "blocker": blocker}
STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "
", encoding="utf-8")
REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
lines = ["# BEM-569 | Mailbox Dispatcher Direct Telegram Result", "", "Дата: workflow_runtime", "", "## Result", "Picked: " + str(pick.get("picked")), "Mailbox file: " + str(pick.get("mailbox_file")), "Direct send status: " + status, "", "## Blocker", "null" if blocker is None else json.dumps(blocker, ensure_ascii=False), ""]
REPORT_PATH.write_text("
".join(lines), encoding="utf-8")
print(json.dumps(state["last_run"], ensure_ascii=False))
