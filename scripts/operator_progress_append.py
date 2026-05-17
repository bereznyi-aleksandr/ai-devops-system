#!/usr/bin/env python3
import json
import sys
from pathlib import Path

FEED = Path("governance/state/operator_progress_feed.jsonl")
CURRENT = Path("governance/state/operator_progress_current.json")
OUTBOX = Path("governance/telegram_outbox.jsonl")

bem = sys.argv[1] if len(sys.argv) > 1 else "UNKNOWN"
status = sys.argv[2] if len(sys.argv) > 2 else "progress"
message = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else status
record = {
    "record_type": "operator_progress_event",
    "bem": bem,
    "status": status,
    "message": message,
    "created_at": "workflow_runtime",
    "blocker": None,
}
FEED.parent.mkdir(parents=True, exist_ok=True)
with FEED.open("a", encoding="utf-8") as f:
    f.write(json.dumps(record, ensure_ascii=False) + "
")
CURRENT.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "
", encoding="utf-8")
telegram = {
    "record_type": "telegram_hourly_report",
    "cycle_id": bem.lower().replace("-", "_") + "_operator_progress",
    "delivery_mode": "operator_progress_feed",
    "canonical": True,
    "status": "ready_to_send",
    "message": bem + " | " + status + " | " + message,
    "created_at": "workflow_runtime",
    "blocker": None,
    "priority": "operator_progress",
}
with OUTBOX.open("a", encoding="utf-8") as f:
    f.write(json.dumps(telegram, ensure_ascii=False) + "
")
print(json.dumps(record, ensure_ascii=False))
