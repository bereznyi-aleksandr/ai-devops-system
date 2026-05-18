#!/usr/bin/env python3
import json
from pathlib import Path
SEP = bytes.fromhex("0a").decode("ascii")
CURATOR_INBOX = Path("governance/curator/inbox")
ROLE_INBOX = Path("governance/role_orchestrator/inbox")
PENDING_DIR = Path("governance/tasks/pending")
STATE_PATH = Path("governance/state/curator_inbox_router_state.json")
TRANSPORT_PATH = Path("governance/transport/results.jsonl")
REPORT_PATH = Path("governance/reports/curator_inbox_router_result.md")
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
def route_for_intake(path, intake):
    decision_id = str(intake.get("decision_id") or path.stem)
    route = {
        "schema_version": "role_orchestrator_intake.v1",
        "record_type": "curator_operator_decision_route",
        "decision_id": decision_id,
        "source_file": str(path),
        "from_role": "curator",
        "to_role": "role_orchestrator",
        "next_route": intake.get("next_route") or "internal_contour",
        "operator_choice": intake.get("operator_choice"),
        "selected_option": intake.get("selected_option"),
        "question": intake.get("question"),
        "status": "ready_for_role_orchestrator",
        "created_at": "workflow_runtime",
        "payload": intake,
    }
    return decision_id, route
state = load_json(STATE_PATH, {})
processed = set(state.get("processed_intakes", []))
CURATOR_INBOX.mkdir(parents=True, exist_ok=True)
ROLE_INBOX.mkdir(parents=True, exist_ok=True)
PENDING_DIR.mkdir(parents=True, exist_ok=True)
created = []
for path in sorted(CURATOR_INBOX.glob("*.json"), key=lambda p: str(p)):
    if str(path) in processed:
        continue
    intake = load_json(path, {})
    decision_id, route = route_for_intake(path, intake)
    out = ROLE_INBOX / ("curator_operator_decision_" + decision_id + ".json")
    save_json(out, route)
    task = PENDING_DIR / ("role_orchestrator_operator_decision_" + decision_id + ".md")
    task.write_text("# Role Orchestrator Intake | Operator Decision" + SEP + SEP + "Decision: " + decision_id + SEP + "Choice: " + str(route.get("operator_choice")) + SEP + "Selected option: " + str(route.get("selected_option")) + SEP + SEP + "Next: route to internal contour according to curator package." + SEP + SEP + "Blocker: null" + SEP, encoding="utf-8")
    append_jsonl(TRANSPORT_PATH, route)
    created.append(str(out))
    processed.add(str(path))
state["processed_intakes"] = sorted(processed)
state["last_run"] = {"created": created, "count": len(created), "status": "completed", "blocker": None}
save_json(STATE_PATH, state)
REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
report = ["# BEM-596 | Curator Inbox Router Result", "", "Дата: workflow_runtime", "", "## Created", json.dumps(created, ensure_ascii=False, indent=2), "", "## Blocker", "null"]
REPORT_PATH.write_text(SEP.join(report) + SEP, encoding="utf-8")
print(json.dumps(state["last_run"], ensure_ascii=False))
