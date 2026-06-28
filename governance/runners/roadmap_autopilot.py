#!/usr/bin/env python3
"""Universal queue-driven roadmap dispatcher.

The dispatcher has no task-ID allowlist. Each pending task supplies an optional
workflow binding in ACTIVE_QUEUE.json; otherwise a deterministic convention is used.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
QUEUE_PATH = ROOT / "governance" / "roadmap" / "ACTIVE_QUEUE.json"
DEFAULT_DEPENDENCY_STATUSES = {
    "DONE",
    "DONE_LIMITED_SCOPE",
    "DONE_STATIC_ONLY",
    "DONE_PREPARED_FOR_EXTERNAL_AUDIT",
    "SKIPPED_BY_OPERATOR",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_queue() -> dict[str, Any]:
    queue = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    if not isinstance(queue, dict) or not isinstance(queue.get("tasks"), list):
        raise ValueError("ACTIVE_QUEUE.json must be an object with a tasks list")
    return queue


def write_queue(queue: dict[str, Any]) -> None:
    QUEUE_PATH.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def tasks_by_id(tasks: list[Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for task in tasks:
        if isinstance(task, dict) and isinstance(task.get("id"), str) and task["id"]:
            result[task["id"]] = task
    return result


def dependency_satisfied(task: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> bool:
    dependencies = task.get("depends_on", [])
    if dependencies is None:
        return True
    if not isinstance(dependencies, list):
        return False

    for dependency in dependencies:
        accepted = set(DEFAULT_DEPENDENCY_STATUSES)
        if isinstance(dependency, str):
            dependency_id = dependency
        elif isinstance(dependency, dict):
            dependency_id = dependency.get("id")
            custom = dependency.get("accepted_statuses")
            if custom is not None:
                if not isinstance(custom, list) or not all(isinstance(value, str) for value in custom):
                    return False
                accepted = {value.upper() for value in custom}
        else:
            return False

        parent = by_id.get(dependency_id) if isinstance(dependency_id, str) else None
        if parent is None or str(parent.get("status", "")).upper() not in accepted:
            return False
    return True


def binding_for(task: dict[str, Any], task_id: str, trace_id: str) -> tuple[str, dict[str, str]]:
    execution = task.get("execution")
    if isinstance(execution, dict):
        kind = str(execution.get("kind", "workflow")).lower()
        if kind != "workflow":
            raise ValueError(f"unsupported execution kind: {kind}")
        workflow_id = execution.get("workflow_id")
        raw_inputs = execution.get("inputs", {})
        if not isinstance(workflow_id, str) or not workflow_id:
            raise ValueError("workflow execution requires workflow_id")
        if not isinstance(raw_inputs, dict):
            raise ValueError("workflow execution inputs must be an object")
        inputs = {
            str(key): str(value).replace("${task_id}", task_id).replace("${trace_id}", trace_id)
            for key, value in raw_inputs.items()
        }
    else:
        # Convention, not a task-ID mapping: any task can declare a matching workflow file.
        workflow_id = f"{task_id.lower()}.yml"
        inputs = {}

    if workflow_id.startswith("/") or ".." in Path(workflow_id).parts:
        raise ValueError("workflow_id must be repository-relative")
    inputs.setdefault("trace_id", trace_id)
    return workflow_id, inputs


def select_pending(tasks: list[Any], by_id: dict[str, dict[str, Any]], force_task_id: str) -> dict[str, Any] | None:
    if force_task_id:
        task = by_id.get(force_task_id)
        if task is None:
            raise ValueError(f"forced task does not exist: {force_task_id}")
        if str(task.get("status", "")).upper() != "PENDING":
            raise ValueError(f"forced task is not PENDING: {force_task_id}")
        if not dependency_satisfied(task, by_id):
            raise ValueError(f"forced task dependencies are not satisfied: {force_task_id}")
        return task

    for task in tasks:
        if (
            isinstance(task, dict)
            and str(task.get("status", "")).upper() == "PENDING"
            and dependency_satisfied(task, by_id)
        ):
            return task
    return None


def main(force_task_id: str) -> dict[str, Any]:
    queue = read_queue()
    tasks = queue["tasks"]
    by_id = tasks_by_id(tasks)

    current_task_id = queue.get("current_task")
    current_task = by_id.get(current_task_id) if isinstance(current_task_id, str) else None
    if current_task and str(current_taskg.get("status", "")).upper() == "IN_PROGRESS":
        return {
            "action": "stop",
            "reason": "active_task_in_progress",
            "task_id": current_task_id,
            "queue_changed": False,
        }

    selected = select_pending(tasks, by_id, force_task_id)
    if selected is None:
        statuses = [str(task.get("status", "")).upper() for task in tasks if isinstance(task, dict)]
        queue["queue_state"] = "BLOCKED" if any(status.startswith("BLOCKED") for status in statuses) else "IDLE"
        queue["updated_at"] = utc_now()
        write_queue(queue)
        return {"action": "stop", "reason": "no_eligible_pending_task", "queue_changed": True}

    task_id = selected["id"]
    trace_id = f"autopilot_{task_id.lower().replace('-', '_')}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    workflow_id, inputs = binding_for(selected, task_id, trace_id)
    selected.update({"status": "IN_PROGRESS", "started_at": utc_now(), "trace_id": trace_id})
    queue.update({"current_task": task_id, "queue_state": "ACTIVE", "updated_at": utc_now()})
    write_queue(queue)
    return {
        "action": "dispatch",
        "task_id": task_id,
        "trace_id": trace_id,
        "workflow_id": workflow_id,
        "inputs": inputs,
        "queue_changed": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Universal queue-driven roadmap dispatcher")
    parser.add_argument("--force-task-id", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = main(args.force_task_id.strip())
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
