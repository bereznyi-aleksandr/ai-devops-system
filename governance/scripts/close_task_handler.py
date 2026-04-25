#!/usr/bin/env python3
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

TASK_PATHS = [
    Path("governance/current_task.json"),
    Path("governance/tasks/TASK-GHA-E2E-001.json"),
]

def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def is_close_candidate(task: dict) -> bool:
    return (
        isinstance(task, dict)
        and str(task.get("next_action", "")) == "CLOSE_TASK"
        and str(task.get("next_role", "")) == "SYSTEM"
        and str(task.get("current_state", "")) in {
            "COMPLETED",
            "COMPLETED_PENDING_CLOSE",
            "READY_TO_CLOSE",
        }
    )

def close_task(task: dict) -> dict:
    updated = deepcopy(task)
    events = updated.get("events")
    if not isinstance(events, list):
        events = []

    events.append({
        "event_id": f"CLOSE-TASK-{len(events) + 1:03d}",
        "created_at": utc_now(),
        "role": "SYSTEM",
        "action": "CLOSE_TASK",
        "result": "TASK_CLOSED_BY_SYSTEM",
    })

    updated["current_state"] = "CLOSED"
    updated["status_bucket"] = "COMPLETED_CLOSED"
    updated["next_role"] = None
    updated["next_action"] = None
    updated["is_terminal"] = True
    updated["closed_by_system"] = True
    updated["closed_at"] = utc_now()
    updated["events"] = events
    return updated

changed = []
closed = False
source_task = {}

for path in TASK_PATHS:
    task = load_json(path)
    if is_close_candidate(task):
        source_task = close_task(task)
        closed = True
        break

if closed:
    task_id = source_task.get("task_id", "")
    for path in TASK_PATHS:
        existing = load_json(path)
        if path.name == "current_task.json" or existing.get("task_id") == task_id:
            save_json(path, source_task)
            changed.append(str(path))

events = source_task.get("events", []) if isinstance(source_task, dict) else []
events_count = len(events) if isinstance(events, list) else 0

print(f"CLOSE_TASK_HANDLER_CLOSED={str(closed).lower()}")
print(f"CLOSE_TASK_HANDLER_CHANGED_FILES={','.join(changed)}")
print(f"CLOSE_TASK_HANDLER_CURRENT_STATE={source_task.get('current_state', '') if source_task else ''}")
print(f"CLOSE_TASK_HANDLER_STATUS_BUCKET={source_task.get('status_bucket', '') if source_task else ''}")
print(f"CLOSE_TASK_HANDLER_IS_TERMINAL={str(source_task.get('is_terminal', False)).lower() if source_task else 'false'}")
print(f"CLOSE_TASK_HANDLER_CLOSED_BY_SYSTEM={str(source_task.get('closed_by_system', False)).lower() if source_task else 'false'}")
print(f"CLOSE_TASK_HANDLER_EVENTS_COUNT={events_count}")
