#!/usr/bin/env python3
import json
from pathlib import Path

PICK = Path("governance/tmp/telegram_pick.json")
TRANSPORT = Path("governance/transport/results.jsonl")
STATE = Path("governance/state/contour_status.json")
STATUS = Path("governance/tmp/telegram_status.txt")

pick = json.loads(PICK.read_text(encoding="utf-8")) if PICK.exists() else {"found": False}
status_text = STATUS.read_text(encoding="utf-8", errors="ignore").strip() if STATUS.exists() else "failed:status_missing"
if not pick.get("found"):
    result = {"sent": 0, "failed": 0, "skipped": 1, "reason": "no_queued_message"}
else:
    ok = status_text == "sent" or status_text == "sent_synthetic"
    delivery = {
        "record_type": "telegram_delivery_result",
        "cycle_id": pick.get("cycle_id"),
        "source": "telegram_sender",
        "from_role": "telegram_sender",
        "to_role": "curator",
        "status": status_text if ok else "failed",
        "outbox_line": pick.get("outbox_line"),
        "message_hash": pick.get("message_hash"),
        "attempt": 1,
        "retry_allowed": not ok,
        "next_retry_at": None if ok else "next_hour",
        "artifact_path": "governance/telegram_outbox.jsonl",
        "commit_sha": None,
        "blocker": None if ok else {"code": "TELEGRAM_DELIVERY_FAILED", "message": status_text},
        "created_at": "workflow_runtime",
    }
    TRANSPORT.parent.mkdir(parents=True, exist_ok=True)
    with TRANSPORT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(delivery, ensure_ascii=False) + "\n")
    result = {"sent": 1 if ok else 0, "failed": 0 if ok else 1, "skipped": 0, "status": delivery["status"]}
state = {}
if STATE.exists():
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        state = {}
state["telegram_sender_last_run"] = result
STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
