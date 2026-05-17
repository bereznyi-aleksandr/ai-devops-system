#!/usr/bin/env python3
import json
from pathlib import Path
SEP = bytes.fromhex("0a").decode("ascii")
STATE_PATH = Path("governance/state/operator_decision_dispatcher_state.json")
PICK_PATH = Path("governance/tmp/operator_decision_pick.json")
STATUS_PATH = Path("governance/tmp/operator_decision_telegram_status.txt")
TRANSPORT_PATH = Path("governance/transport/results.jsonl")
REPORT_PATH = Path("governance/reports/operator_decision_dispatch_result.md")
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
        handle.write(json.dumps(record, ensure_ascii=False) + SEP)
state = load_json(STATE_PATH, {})
pick = load_json(PICK_PATH, {"picked": False, "send": False})
status = STATUS_PATH.read_text(encoding="utf-8", errors="ignore").strip() if STATUS_PATH.exists() else "not_required"
if pick.get("picked"):
    processed = set(state.get("processed_items", []))
    processed.add(pick.get("queue_file"))
    state["processed_items"] = sorted(processed)
record = {"record_type":"operator_decision_dispatch","cycle_id":"bem584-fix-decision-renderer-no-newline-literal","queue_file":pick.get("queue_file"),"decision_id":pick.get("decision_id"),"send":pick.get("send"),"reason":pick.get("reason"),"telegram_status":status if pick.get("send") else "not_sent","created_at":"workflow_runtime","blocker":None if (not pick.get("send") or status == "sent") else {"code":"OPERATOR_DECISION_TELEGRAM_NOT_SENT","status":status}}
append_jsonl(TRANSPORT_PATH, record)
state["last_run"] = record
STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + SEP, encoding="utf-8")
REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
REPORT_PATH.write_text("# Operator Decision Dispatch Result" + SEP + SEP + json.dumps(record, ensure_ascii=False, indent=2) + SEP, encoding="utf-8")
print(json.dumps(record, ensure_ascii=False))
