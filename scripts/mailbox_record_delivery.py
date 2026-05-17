#!/usr/bin/env python3
import json
from pathlib import Path

NL = "\n"
STATE_PATH = Path("governance/state/mailbox_dispatcher_state.json")
PICK_PATH = Path("governance/tmp/mailbox_pick.json")
TRANSPORT_PATH = Path("governance/transport/results.jsonl")
REPORT_PATH = Path("governance/reports/mailbox_dispatcher_result.md")

def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default

def append_jsonl(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + NL)

state = load_json(STATE_PATH, {})
pick = load_json(PICK_PATH, {"picked": False, "mailbox_file": None, "reason": "missing_pick"})
if pick.get("picked"):
    processed = set(state.get("processed_files", []))
    processed.add(pick.get("mailbox_file"))
    state["processed_files"] = sorted(processed)
record = {
    "record_type": "mailbox_dispatcher_route",
    "cycle_id": "bem579-fix-mailbox-no-chr",
    "mailbox_file": pick.get("mailbox_file"),
    "notify_operator": False,
    "reason": pick.get("reason"),
    "telegram_status": "not_required",
    "created_at": "workflow_runtime",
    "blocker": None,
}
append_jsonl(TRANSPORT_PATH, record)
state["last_run"] = record
STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + NL, encoding="utf-8")
REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
report_lines = [
    "# BEM-579 | Mailbox Dispatcher Result",
    "",
    "Дата: workflow_runtime",
    "",
    "## Result",
    "Picked: " + str(pick.get("picked")),
    "Mailbox file: " + str(pick.get("mailbox_file")),
    "Notify operator: False",
    "Reason: " + str(pick.get("reason")),
    "",
    "## Blocker",
    "null",
]
REPORT_PATH.write_text(NL.join(report_lines) + NL, encoding="utf-8")
print(json.dumps(record, ensure_ascii=False))
