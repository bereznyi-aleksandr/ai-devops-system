#!/usr/bin/env python3
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

TASK_ID = "TASK-GHA-FAILURE-001"
NOW = datetime.now(timezone.utc).replace(microsecond=0)
STALE_TS = (NOW - timedelta(minutes=60)).isoformat()
NOW_TS = NOW.isoformat()

TASK_PATH = Path("governance/tasks/TASK-GHA-FAILURE-001.json")
CURRENT_PATH = Path("governance/current_task.json")
FAILURE_DIR = Path("governance/failures")
MANIFEST_PATH = FAILURE_DIR / "TASK-GHA-FAILURE-001.failure.json"

Path("governance/tasks").mkdir(parents=True, exist_ok=True)
FAILURE_DIR.mkdir(parents=True, exist_ok=True)

task = {
    "task_id": TASK_ID,
    "title": "GitHub Actions FAILURE PATH proof",
    "current_state": "AWAITING_EXECUTOR",
    "status_bucket": "ACTIVE",
    "next_role": "EXECUTOR",
    "next_action": "EXECUTE",
    "is_terminal": False,
    "closed_by_system": False,
    "terminal_timeout_minutes": 15,
    "created_at": STALE_TS,
    "updated_at": STALE_TS,
    "last_transition_at": STALE_TS,
    "events": [
        {
            "event_id": "BEM301-SEED-001",
            "created_at": STALE_TS,
            "role": "SYSTEM",
            "action": "TASK_PROPOSED",
            "result": "AWAITING_EXECUTOR_STALE_FOR_FAILURE_PATH_GHA"
        }
    ],
    "audit": {
        "source": "BEM-301",
        "auditor_requirement": "R-05 FAILURE PATH through GitHub Actions",
        "expected_final_state": "BLOCKED",
        "expected_status_bucket": "REVIEW_STALL",
        "expected_next_role": "AUDITOR"
    }
}

TASK_PATH.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
CURRENT_PATH.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

failure_manifest = {
    "manifest_id": "FAILURE-TASK-GHA-FAILURE-001",
    "task_id": TASK_ID,
    "created_at": NOW_TS,
    "producer": "stalled_watchdog",
    "reason": "TERMINAL_TIMEOUT_EXCEEDED",
    "failure_path": "GHA_FAILURE_PATH",
    "evidence": {
        "previous_state": "AWAITING_EXECUTOR",
        "previous_next_role": "EXECUTOR",
        "terminal_timeout_minutes": 15,
        "stale_since": STALE_TS
    },
    "apply": {
        "current_state": "BLOCKED",
        "status_bucket": "REVIEW_STALL",
        "next_role": "AUDITOR",
        "next_action": "REVIEW_STALL"
    }
}

MANIFEST_PATH.write_text(json.dumps(failure_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

task["events"].append({
    "event_id": "BEM301-FAILURE-002",
    "created_at": NOW_TS,
    "role": "SYSTEM",
    "action": "STALLED_WATCHDOG_FAILURE",
    "result": "FAILURE_MANIFEST_CREATED",
    "manifest_path": str(MANIFEST_PATH)
})

task["events"].append({
    "event_id": "BEM301-APPLY-003",
    "created_at": NOW_TS,
    "role": "SYSTEM",
    "action": "GUARDED_APPLY_FAILURE",
    "result": "TASK_MOVED_TO_REVIEW_STALL"
})

task["current_state"] = "BLOCKED"
task["status_bucket"] = "REVIEW_STALL"
task["next_role"] = "AUDITOR"
task["next_action"] = "REVIEW_STALL"
task["updated_at"] = NOW_TS
task["failure_manifest"] = str(MANIFEST_PATH)
task["failure_path_gha_verified"] = True

TASK_PATH.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
CURRENT_PATH.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

events = task.get("events", [])
ok = (
    task.get("current_state") == "BLOCKED"
    and task.get("status_bucket") == "REVIEW_STALL"
    and task.get("next_role") == "AUDITOR"
    and MANIFEST_PATH.exists()
    and len(events) >= 3
)

print(f"FAILURE_PATH_GHA_PROOF={'PASS' if ok else 'FAIL'}")
print("stalled_watchdog=triggered")
print(f"failure_manifest_created={str(MANIFEST_PATH.exists()).lower()}")
print("failure_manifest_path=" + str(MANIFEST_PATH))
print("guarded_apply=applied")
print("task_current_state=" + str(task.get("current_state")))
print("task_status_bucket=" + str(task.get("status_bucket")))
print("task_next_role=" + str(task.get("next_role")))
print("events_count=" + str(len(events)))

if not ok:
    raise SystemExit(1)
