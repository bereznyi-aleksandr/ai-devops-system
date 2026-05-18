#!/usr/bin/env python3
import json
from pathlib import Path
SEP = bytes.fromhex("0a").decode("ascii")
DECISIONS_DIR = Path("governance/operator_decisions")
CURATOR_INBOX = Path("governance/curator/inbox")
STATE_PATH = Path("governance/state/decision_curator_handoff_state.json")
TRANSPORT_PATH = Path("governance/transport/results.jsonl")
REPORT_PATH = Path("governance/reports/decision_curator_handoff_result.md")
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
state = load_json(STATE_PATH, {})
processed = set(state.get("processed_decisions", []))
DECISIONS_DIR.mkdir(parents=True, exist_ok=True)
CURATOR_INBOX.mkdir(parents=True, exist_ok=True)
created = []
for path in sorted(DECISIONS_DIR.glob("*.json"), key=lambda p: str(p)):
    if str(path) in processed:
        continue
    decision = load_json(path, {})
    decision_id = str(decision.get("decision_id") or path.stem)
    intake = {
        "schema_version": "curator_intake.operator_decision.v1",
        "record_type": "operator_decision_curator_intake",
        "decision_id": decision_id,
        "source_file": str(path),
        "operator_choice": decision.get("operator_choice"),
        "selected_option": decision.get("selected_option"),
        "question": decision.get("question"),
        "handoff_to": "curator",
        "next_route": "internal_contour",
        "status": "ready_for_curator",
        "created_at": "workflow_runtime",
        "decision": decision,
    }
    out = CURATOR_INBOX / ("operator_decision_" + decision_id + ".json")
    save_json(out, intake)
    created.append(str(out))
    processed.add(str(path))
    append_jsonl(TRANSPORT_PATH, intake)
state["processed_decisions"] = sorted(processed)
state["last_run"] = {"created": created, "count": len(created), "status": "completed", "blocker": None}
save_json(STATE_PATH, state)
report = ["# BEM-593 | Decision Curator Handoff Result", "", "Дата: workflow_runtime", "", "## Created", json.dumps(created, ensure_ascii=False, indent=2), "", "## Blocker", "null"]
REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
REPORT_PATH.write_text(SEP.join(report) + SEP, encoding="utf-8")
print(json.dumps(state["last_run"], ensure_ascii=False))
