#!/usr/bin/env python3
import json
from pathlib import Path
SEP = bytes.fromhex("0a").decode("ascii")
UPDATES_PATH = Path("governance/tmp/operator_reply_updates.json")
STATUS_PATH = Path("governance/tmp/operator_reply_status.txt")
STATE_PATH = Path("governance/state/operator_reply_intake_state.json")
DISPATCH_STATE_PATH = Path("governance/state/operator_decision_dispatcher_state.json")
DECISIONS_DIR = Path("governance/operator_decisions")
HANDOFF_DIR = Path("governance/tasks/pending")
TRANSPORT_PATH = Path("governance/transport/results.jsonl")
REPORT_PATH = Path("governance/reports/operator_reply_intake_result.md")
def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default
def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + SEP, encoding="utf-8")
def append_jsonl(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + SEP)
def active_decision_id():
    st = load_json(DISPATCH_STATE_PATH, {})
    last = st.get("last_run") if isinstance(st, dict) else None
    if isinstance(last, dict) and last.get("decision_id"):
        return str(last.get("decision_id"))
    return "unknown_decision"
def normalize_choice(text):
    raw = " ".join(str(text or "").strip().split())
    low = raw.lower()
    if low in ["1", "1.", "1)", "да", "так", "yes", "y", "подтверждаю", "approve", "approved"]:
        return "1", raw
    if low in ["2", "2.", "2)", "нет", "no", "n", "доработать", "на доработку", "reject", "rework"]:
        return "2", raw
    if low in ["3", "3.", "3)", "свой", "свой вариант", "custom"]:
        return "3", raw
    if raw:
        return "custom", raw
    return None, raw
def extract_updates(data):
    result = data.get("result") if isinstance(data, dict) else []
    return result if isinstance(result, list) else []
def main():
    status = STATUS_PATH.read_text(encoding="utf-8", errors="ignore").strip() if STATUS_PATH.exists() else "missing_status"
    updates = load_json(UPDATES_PATH, {})
    state = load_json(STATE_PATH, {})
    seen = set(state.get("seen_update_ids", []))
    chosen = None
    max_update_id = state.get("last_update_id", 0)
    for upd in extract_updates(updates):
        uid = upd.get("update_id")
        if uid is not None:
            try:
                max_update_id = max(int(max_update_id), int(uid))
            except Exception:
                pass
        if str(uid) in seen:
            continue
        msg = upd.get("message") or upd.get("edited_message") or {}
        text = msg.get("text") or ""
        choice, raw = normalize_choice(text)
        if choice:
            chosen = {"update_id": uid, "message": msg, "choice": choice, "raw_text": raw}
    record = None
    blocker = None
    if chosen is None:
        status_out = "no_operator_reply_found"
    else:
        decision_id = active_decision_id()
        DECISIONS_DIR.mkdir(parents=True, exist_ok=True)
        HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
        rec = {
            "schema_version": "operator_decision.v1",
            "decision_id": decision_id,
            "source": "telegram_text_reply",
            "operator_choice": chosen.get("choice"),
            "raw_text": chosen.get("raw_text"),
            "telegram_update_id": chosen.get("update_id"),
            "status": "received",
            "handoff_to": "curator",
            "created_at": "workflow_runtime"
        }
        decision_path = DECISIONS_DIR / (decision_id + ".json")
        save_json(decision_path, rec)
        handoff = HANDOFF_DIR / ("operator_decision_" + decision_id + ".md")
        handoff.write_text("# Operator decision handoff" + SEP + SEP + "Decision: " + decision_id + SEP + "Choice: " + str(rec.get("operator_choice")) + SEP + "Raw: " + str(rec.get("raw_text")) + SEP + SEP + "Next: curator must route this decision into the internal contour." + SEP, encoding="utf-8")
        record = rec
        status_out = "operator_decision_recorded"
    for upd in extract_updates(updates):
        if upd.get("update_id") is not None:
            seen.add(str(upd.get("update_id")))
    state["seen_update_ids"] = sorted(seen)
    state["last_update_id"] = max_update_id
    state["last_run"] = {"http_status": status, "status": status_out, "record": record, "blocker": blocker}
    save_json(STATE_PATH, state)
    tr = {"record_type":"operator_reply_intake","cycle_id":"bem586-operator-reply-intake-poller","status":status_out,"http_status":status,"record":record,"blocker":blocker,"created_at":"workflow_runtime"}
    append_jsonl(TRANSPORT_PATH, tr)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("# BEM-586 | Operator Reply Intake Result" + SEP + SEP + json.dumps(tr, ensure_ascii=False, indent=2) + SEP, encoding="utf-8")
    print(json.dumps(tr, ensure_ascii=False))
if __name__ == "__main__":
    main()
