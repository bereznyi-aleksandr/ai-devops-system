#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = ROOT / "governance" / "runtime" / "tasks" / "index.json"


class OrchestratorV2Error(RuntimeError):
    pass


PRIORITY_ORDER = [
    "AWAITING_SYSTEM",
    "AWAITING_AUDITOR",
    "AWAITING_EXECUTOR",
    "IN_PROGRESS",
    "APPROVED",
    "BLOCKED",
    "UNKNOWN",
    "INVALID",
    "COMPLETED_OPEN_TERMINAL",
]

PRIORITY_RANK = {name: i for i, name in enumerate(PRIORITY_ORDER)}


def read_index() -> Dict[str, object]:
    if not INDEX_PATH.exists():
        raise OrchestratorV2Error("Task index file does not exist")
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def normalize_items(raw_items: List[Dict[str, object]]) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    for item in raw_items:
        items.append(
            {
                "task_id": str(item.get("task_id", "")),
                "registry_path": str(item.get("registry_path", "")),
                "current_state": str(item.get("current_state", "")),
                "last_event_type": str(item.get("last_event_type", "")),
                "next_role": str(item.get("next_role", "")),
                "next_action": str(item.get("next_action", "")),
                "last_event_ts": str(item.get("last_event_ts", "")),
                "status_bucket": str(item.get("status_bucket", "UNKNOWN")),
                "is_terminal": str(item.get("is_terminal", "")).lower(),
                "closed_by_system": str(item.get("closed_by_system", "")).lower(),
            }
        )
    return items


def is_closed(item: Dict[str, str]) -> bool:
    return item.get("status_bucket", "") == "COMPLETED_CLOSED"


def priority_key(item: Dict[str, str]) -> Tuple[int, str, str]:
    bucket = item.get("status_bucket", "UNKNOWN")
    rank = PRIORITY_RANK.get(bucket, 999)
    ts = item.get("last_event_ts", "")
    task_id = item.get("task_id", "")
    return (rank, ts, task_id)


def infer_priority_reason(item: Dict[str, str]) -> str:
    bucket = item.get("status_bucket", "UNKNOWN")
    next_role = item.get("next_role", "")
    next_action = item.get("next_action", "")

    if bucket == "AWAITING_SYSTEM":
        return f"Task is waiting on SYSTEM to perform {next_action}."
    if bucket == "AWAITING_AUDITOR":
        return f"Task is waiting on AUDITOR to perform {next_action}."
    if bucket == "AWAITING_EXECUTOR":
        return f"Task is waiting on EXECUTOR to perform {next_action}."
    if bucket == "IN_PROGRESS":
        return "Task is in progress and not yet routed to a terminal bucket."
    if bucket == "APPROVED":
        return "Task is approved and may require downstream execution."
    if bucket == "BLOCKED":
        return "Task is blocked and may need intervention."
    if bucket == "COMPLETED_OPEN_TERMINAL":
        return "Task is terminal but not system-closed."
    return f"Task selected from fallback bucket {bucket}."

def main() -> int:
    try:
        index_doc = read_index()
        raw_items = index_doc.get("items", [])
        if not isinstance(raw_items, list):
            raise OrchestratorV2Error("Index items is not a list")

        items = normalize_items(raw_items)
        candidates = [item for item in items if not is_closed(item) and item.get('status_bucket', 'UNKNOWN') != 'UNKNOWN']

        if not candidates:
            report = {
                "system_orchestrator_version": "v2",
                "result": "NO_WORK",
                "index_path": str(INDEX_PATH.relative_to(ROOT)),
                "candidate_count": 0,
                "message": "No non-closed tasks available for orchestration.",
            }
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        candidates.sort(key=priority_key)
        chosen = candidates[0]

        report = {
            "system_orchestrator_version": "v2",
            "result": "READY",
            "index_path": str(INDEX_PATH.relative_to(ROOT)),
            "candidate_count": len(candidates),
            "selected_task": {
                "task_id": chosen["task_id"],
                "status_bucket": chosen["status_bucket"],
                "current_state": chosen["current_state"],
                "last_event_type": chosen["last_event_type"],
                "next_role": chosen["next_role"],
                "next_action": chosen["next_action"],
                "last_event_ts": chosen["last_event_ts"],
                "registry_path": chosen["registry_path"],
                "priority_reason": infer_priority_reason(chosen),
            },
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    except Exception as e:
        print(
            json.dumps(
                {
                    "system_orchestrator_version": "v2",
                    "result": "BLOCKED",
                    "error": str(e),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
