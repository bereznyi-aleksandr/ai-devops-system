#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "governance" / "scripts"
TASKS_DIR = ROOT / "governance" / "runtime" / "tasks"
RESULTS_DIR = ROOT / "governance" / "runtime" / "results"
INDEX_PATH = TASKS_DIR / "index.json"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from system_transition_map_v1 import resolve_success_transition  # noqa: E402


class ApplyResultError(RuntimeError):
    pass


RESULT_CANDIDATES = [
    "executor_write_plan_result.json",
    "executor_materialize_result.json",
    "auditor_materialize_result.json",
    "system_close_result.json",
]


def read_json(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def choose_latest_result() -> Tuple[Path, Dict[str, object]]:
    found: List[Tuple[str, Path, Dict[str, object]]] = []
    for name in RESULT_CANDIDATES:
        path = RESULTS_DIR / name
        if path.exists():
            data = read_json(path)
            ts = str(data.get("ts_utc", ""))
            found.append((ts, path, data))

    if not found:
        raise ApplyResultError("No known result manifests found in governance/runtime/results")

    found.sort(key=lambda x: x[0])
    _, path, data = found[-1]
    return path, data


def registry_path_for(task_id: str) -> Path:
    return TASKS_DIR / f"{task_id}.json"


def load_registry(task_id: str) -> Dict[str, object]:
    path = registry_path_for(task_id)
    if not path.exists():
        raise ApplyResultError(f"Registry not found for task: {task_id}")
    return read_json(path)


def write_registry(task_id: str, data: Dict[str, object]) -> Path:
    path = registry_path_for(task_id)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def infer_status_bucket(item: Dict[str, object]) -> str:
    current_state = str(item.get("current_state", ""))
    next_role = str(item.get("next_role", ""))
    is_terminal = bool(item.get("is_terminal", False))
    closed_by_system = bool(item.get("closed_by_system", False))

    if is_terminal and closed_by_system:
        return "COMPLETED_CLOSED"
    if is_terminal:
        return "COMPLETED_OPEN_TERMINAL"
    if next_role == "EXECUTOR":
        return "AWAITING_EXECUTOR"
    if next_role == "AUDITOR":
        return "AWAITING_AUDITOR"
    if next_role == "SYSTEM":
        return "AWAITING_SYSTEM"
    if current_state.endswith("PENDING"):
        return "IN_PROGRESS"
    if current_state.endswith("APPROVED"):
        return "APPROVED"
    if current_state.endswith("BLOCKED"):
        return "BLOCKED"
    return "UNKNOWN"


def rebuild_index() -> Dict[str, object]:
    items: List[Dict[str, object]] = []

    for path in sorted(TASKS_DIR.glob('*.json')):
        if path.name == 'index.json':
            continue

        data = read_json(path)
        task_id = str(data.get('task_id', '')).strip()
        if not task_id:
            continue

        item = {
            'task_id': task_id,
            'registry_path': str(path.relative_to(ROOT)),
            'current_state': str(data.get('current_state', '')).strip(),
            'last_event_type': str(data.get('last_event_type', '')).strip(),
            'next_role': str(data.get('next_role', '')).strip(),
            'next_action': str(data.get('next_action', '')).strip(),
            'is_terminal': bool(data.get('is_terminal', False)),
            'closed_by_system': bool(data.get('closed_by_system', False)),
            'last_event_ts': str(data.get('last_event_ts', '')).strip(),
            'status_bucket': infer_status_bucket(data),
        }
        items.append(item)

    latest: Dict[str, Dict[str, object]] = {}
    for item in items:
        task_id = str(item.get('task_id', '')).strip()
        ts = str(item.get('last_event_ts', '')).strip()
        prev = latest.get(task_id)
        if prev is None or (ts, task_id) > (str(prev.get('last_event_ts', '')).strip(), task_id):
            latest[task_id] = item

    items = sorted(
        latest.values(),
        key=lambda x: (str(x.get('last_event_ts', '')).strip(), str(x.get('task_id', '')).strip()),
        reverse=True,
    )

    summary: Dict[str, int] = {}
    for item in items:
        bucket = str(item.get('status_bucket', 'UNKNOWN')).strip() or 'UNKNOWN'
        summary[bucket] = summary.get(bucket, 0) + 1
    summary['TOTAL'] = len(items)

    index_doc = {
        'system_task_index_version': 'v1',
        'result': 'SUCCESS',
        'tasks_dir': str(TASKS_DIR.relative_to(ROOT)),
        'index_path': str(INDEX_PATH.relative_to(ROOT)),
        'summary': summary,
        'items': items,
    }

    INDEX_PATH.write_text(json.dumps(index_doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return index_doc

def apply_executor_success(task_id: str, registry: Dict[str, object], result_path: Path, result_data: Dict[str, object]) -> Dict[str, object]:
    event_type, new_state, next_role, next_action = resolve_success_transition("EXECUTOR", result_data)

    prev_event_id = str(registry.get("last_event_id", "")).strip()
    new_event_id = f"{event_type}-{task_id}-AUTO-0001"
    ts_utc = str(result_data.get("ts_utc", ""))
    artifact_ref = str(result_data.get("produced_artifact_path", "")).strip()

    registry["current_state"] = new_state
    registry["last_event_id"] = new_event_id
    registry["last_parent_event_id"] = prev_event_id
    registry["last_event_type"] = event_type
    registry["last_actor_role"] = "EXECUTOR"
    registry["last_event_ts"] = ts_utc
    registry["last_summary"] = str(result_data.get("summary", "")).strip()
    registry["next_role"] = next_role
    registry["next_action"] = next_action
    registry["latest_artifact_ref"] = artifact_ref
    registry["latest_commit_sha"] = "LOCAL"
    registry["latest_result_role"] = "EXECUTOR"
    registry["latest_result_manifest"] = str(result_path.relative_to(ROOT))
    registry["latest_result_value"] = str(result_data.get("result", ""))
    registry["latest_result_ts"] = ts_utc
    registry["is_terminal"] = False
    registry["terminal_reason"] = ""

    produced_type = str(result_data.get("produced_artifact_type", "")).strip().lower()
    if produced_type == "plan":
        registry["last_plan_ref"] = artifact_ref
        registry["plan_written"] = True
        registry["plan_written_at"] = ts_utc

    return registry


def apply_auditor_success(task_id: str, registry: Dict[str, object], result_path: Path, result_data: Dict[str, object]) -> Dict[str, object]:
    event_type, new_state, next_role, next_action = resolve_success_transition("AUDITOR", result_data)

    prev_event_id = str(registry.get("last_event_id", "")).strip()
    new_event_id = f"{event_type}-{task_id}-AUTO-0001"
    ts_utc = str(result_data.get("ts_utc", ""))
    artifact_ref = str(result_data.get("produced_artifact_path", "")).strip()

    registry["current_state"] = new_state
    registry["last_event_id"] = new_event_id
    registry["last_parent_event_id"] = prev_event_id
    registry["last_event_type"] = event_type
    registry["last_actor_role"] = "AUDITOR"
    registry["last_event_ts"] = ts_utc
    registry["last_summary"] = str(result_data.get("summary", "")).strip()
    registry["next_role"] = next_role
    registry["next_action"] = next_action
    registry["latest_artifact_ref"] = artifact_ref
    registry["latest_commit_sha"] = "LOCAL"
    registry["latest_result_role"] = "AUDITOR"
    registry["latest_result_manifest"] = str(result_path.relative_to(ROOT))
    registry["latest_result_value"] = str(result_data.get("result", ""))
    registry["latest_result_ts"] = ts_utc
    registry["is_terminal"] = (new_state == "COMPLETED" and next_role == "SYSTEM" and next_action == "CLOSE_TASK")
    registry["terminal_reason"] = "COMPLETED/CLOSE_TASK" if registry["is_terminal"] else ""

    registry["last_decision"] = "APPROVE"
    reviewed_ref = str(result_data.get("reviewed_ref", "")).strip()
    if reviewed_ref:
        registry["reviewed_ref"] = reviewed_ref

    return registry


def main() -> int:
    try:
        result_path, result_data = choose_latest_result()

        role = str(result_data.get("role", "")).strip().upper()
        result_value = str(result_data.get("result", "")).strip().upper()
        task_id = str(result_data.get("task_id", "")).strip()

        if not task_id:
            raise ApplyResultError("Latest result manifest is missing task_id")
        if result_value != "SUCCESS":
            raise ApplyResultError(f"Only SUCCESS result apply is supported in v1, got {result_value!r}")

        registry = load_registry(task_id)

        if role == "EXECUTOR":
            registry = apply_executor_success(task_id, registry, result_path, result_data)
        elif role == "AUDITOR":
            registry = apply_auditor_success(task_id, registry, result_path, result_data)
        else:
            raise ApplyResultError(f"Unsupported role for apply_result_v1: {role!r}")

        registry_path = write_registry(task_id, registry)
        index_doc = rebuild_index()

        report = {
            "system_apply_result_version": "v1",
            "result": "SUCCESS",
            "applied_result_manifest": str(result_path.relative_to(ROOT)),
            "task_id": task_id,
            "role": role,
            "registry_path": str(registry_path.relative_to(ROOT)),
            "current_state": str(registry.get("current_state", "")),
            "last_event_type": str(registry.get("last_event_type", "")),
            "next_role": str(registry.get("next_role", "")),
            "next_action": str(registry.get("next_action", "")),
            "status_bucket": infer_status_bucket(registry),
            "index_summary": index_doc.get("summary", {}),
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    except Exception as e:
        print(
            json.dumps(
                {
                    "system_apply_result_version": "v1",
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
