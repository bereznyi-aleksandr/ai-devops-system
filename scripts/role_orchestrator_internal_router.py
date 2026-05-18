#!/usr/bin/env python3
import json
from pathlib import Path
SEP = bytes.fromhex("0a").decode("ascii")
ROLE_INBOX = Path("governance/role_orchestrator/inbox")
INTERNAL_INBOX = Path("governance/internal_contour/inbox")
INTERNAL_TASKS = Path("governance/internal_contour/tasks")
PENDING_DIR = Path("governance/tasks/pending")
STATE_PATH = Path("governance/state/role_orchestrator_internal_router_state.json")
TRANSPORT_PATH = Path("governance/transport/results.jsonl")
REPORT_PATH = Path("governance/reports/role_orchestrator_internal_router_result.md")
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
def make_internal_job(path, package):
    decision_id = str(package.get("decision_id") or path.stem)
    selected = package.get("selected_option") or package.get("operator_choice")
    job = {
        "schema_version": "internal_contour_intake.v1",
        "record_type": "operator_decision_internal_task",
        "decision_id": decision_id,
        "source_file": str(path),
        "from_role": "role_orchestrator",
        "to_role": "analyst",
        "status": "ready_for_internal_contour",
        "task_type": "apply_operator_decision",
        "summary": "Apply operator decision to system canon and implementation",
        "operator_choice": package.get("operator_choice"),
        "selected_option": selected,
        "question": package.get("question"),
        "acceptance_criteria": [
            "Canonical protocol updated",
            "Runtime renderer follows selected operator decision format",
            "Routine mailbox does not notify Telegram",
            "Operator decision uses structured package only",
            "Evidence recorded in reports and transport",
        ],
        "roles": {"curator":"gpt", "analyst":"gpt", "auditor":"claude", "executor":"claude_or_python_executor"},
        "created_at": "workflow_runtime",
        "payload": package,
    }
    return decision_id, job
state = load_json(STATE_PATH, {})
processed = set(state.get("processed_role_packages", []))
ROLE_INBOX.mkdir(parents=True, exist_ok=True)
INTERNAL_INBOX.mkdir(parents=True, exist_ok=True)
INTERNAL_TASKS.mkdir(parents=True, exist_ok=True)
PENDING_DIR.mkdir(parents=True, exist_ok=True)
created = []
for path in sorted(ROLE_INBOX.glob("*.json"), key=lambda p: str(p)):
    if str(path) in processed:
        continue
    package = load_json(path, {})
    decision_id, job = make_internal_job(path, package)
    inbox_file = INTERNAL_INBOX / ("operator_decision_" + decision_id + ".json")
    task_file = INTERNAL_TASKS / ("operator_decision_" + decision_id + ".json")
    pending_file = PENDING_DIR / ("internal_contour_operator_decision_" + decision_id + ".md")
    save_json(inbox_file, job)
    save_json(task_file, job)
    pending_file.write_text("# Internal Contour Task | Operator Decision" + SEP + SEP + "Decision: " + decision_id + SEP + "Selected: " + str(job.get("selected_option")) + SEP + "Next role: Analyst" + SEP + SEP + "Goal: apply selected operator decision format to canon and runtime implementation." + SEP + SEP + "Blocker: null" + SEP, encoding="utf-8")
    append_jsonl(TRANSPORT_PATH, job)
    created.append({"inbox": str(inbox_file), "task": str(task_file), "pending": str(pending_file)})
    processed.add(str(path))
state["processed_role_packages"] = sorted(processed)
state["last_run"] = {"created": created, "count": len(created), "status": "completed", "blocker": None}
save_json(STATE_PATH, state)
REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
report = ["# BEM-598 | Role Orchestrator Internal Router Result", "", "Дата: workflow_runtime", "", "## Created", json.dumps(created, ensure_ascii=False, indent=2), "", "## Blocker", "null"]
REPORT_PATH.write_text(SEP.join(report) + SEP, encoding="utf-8")
print(json.dumps(state["last_run"], ensure_ascii=False))
