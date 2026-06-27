#!/usr/bin/env python3
"""Universal queue-driven roadmap dispatcher: no task-ID allowlist."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "governance/roadmap/ACTIVE_QUEUE.json"
DISPATCH_LOG = ROOT / "governance/state/dispatch_executed.jsonl"

DEFAULT_DEPENDENCY_STATUSES = {"DONE", "DONE_LIMITED_SCOPE", "SKIPPED_BY_OPERATOR"}
RECEIPT_PASS = {"PASS", "DONE"}
RECEIPT_BLOCK = {"BLOCKED", "FAIL", "FAILED", "ERROR"}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def dump(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data).encode("ascii") + b"\0" + data).hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def save_if_changed(path: Path, value: dict[str, Any], before: bytes) -> bool:
    after = dump(value)
    if after == before:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(after)
    return True


def task_map(tasks: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(tasks, list):
        raise ValueError("ACTIVE_QUEUE.tasks must be a list")
    result: dict[str, dict[str, Any]] = {}
    for task in tasks:
        if isinstance(task, dict) and isinstance(task.get("id"), str) and task["id"]:
            result[task["id"]] = task
    return result

def receipt_outcome(task: dict[str, Any]) -> tuple[str | None, str | None]:
    reference = task.get("receipt")
    if not isinstance(reference, str) or not reference:
        return None, None
    path = (ROOT / reference).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError:
        return "BLOCKED", "receipt_path_outside_repository"
    if not path.is_file():
        return None, None
    try:
        receipt = load_object(path)
    except Exception:
        return "BLOCKED", "unreadable_receipt"
    status = str(receipt.get("status", "")).upper()
    if status in RECEIPT_PASS:
        return "DONE", None
    if status in RECEIPT_BLOCK:
        return "BLOCKED", f"receipt_status_{status.lower()}"
    return None, None

def dependency_spec(value: Any) -> tuple[str, set[str]]:
    if isinstance(value, str):
        return value, set(DEFAULT_DEPENDENCY_STATUSES)
    if isinstance(value, dict):
        task_id = value.get("id")
        statuses = value.get("accepted_statuses", list(DEFAULT_DEPENDENCY_STATUSES))
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("dependency object requires id")
        if not isinstance(statuses, list) or not all(isinstance(s, str) and s for s in statuses):
            raise ValueError("dependency accepted_statuses must be a non-empty string list")
        return task_id, {s.upper() for s in statuses}
    raise ValueError("dependencies must contain task IDs or dependency objects")

def deps_ok(task: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> bool:
    dependencies = task.get("depends_on", [])
    if dependencies is None:
        return True
    if not isinstance(dependencies, list):
        return False
    for dependency in dependencies:
        dep_id, accepted = dependency_spec(dependency)
        parent = by_id.get(dep_id)
        if parent is None or str(parent.get("status", "")).upper() not in accepted:
            return False
    return True

def render(value: Any, task_id: str, trace_id: str) -> str:
    return str(value).replace("${task_id}", task_id).replace("${trace_id}", trace_id)

def dispatch_binding(task: dict[str, Any], task_id: str, trace_id: str) -> tuple[str, dict[str, str]]:
    execution = task.get("execution")
    if isinstance(execution, dict) and str(execution.get("kind", "")).lower() == "workflow":
        workflow_id = execution.get("workflow_id")
        inputs = exection.get("inputs", {})
        if not isinstance(workflow_id, str) or not workflow_id:
            raise ValueError("workflow execution requires workflow_id")
        if workflow_id.startswith("/") or ".." in Path(workflow_id).parts:
            raise ValueError("workflow_id must be repository-relative")
        if not isinstance(inputs, dict):
            raise ValueError("workflow inputs must be an object")
        return workflow_id, {str(k): render(v, task_id, trace_id) for k, v in inputs.items()}
    return "roadmap-task-executor.yml", {"task_id": task_id, "trace_id": trace_id}

def append_dispatch_log(record: dict[str, Any]) -> None:
    DISPATCH_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DISPATCH_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

def select_task(tasks: list[Any], by_id: dict[str, dict[str, Any]], forced: str) -> dict[str, Any] | None:
    if forced:
        task = by_id.get(forced)
        if task is None:
            raise ValueError(f"forced task does not exist: {forced}")
        if str(task.get("status", "")).upper() != "PENDING":
            raise ValueError(f"forced task is not PENDING: {forced}")
        if not deps_ok(task, by_id):
            raise ValueError(f"forced task dependencies are not satisfied: {forced}")
        return task
    for task in tasks:
        if isinstance(task, dict) and str(task.get("status", "")).upper() == "PENDING" and deps_ok(task, by_id):
            return task
    return None

def main(force_task_id: str, trace_prefix: str, dispatch_out: Path) -> dict[str, Any]:
    before = QUEUE.read_bytes()
    queue = load_object(QUEUE)
    tasks = queue.get("tasks")
    by_id = task_map(tasks)
    assert isinstance(tasks, list)

    changed = False
    reconciled: list[str] = []
    for task in tasks:
        if not isinstance(task, dict) or str(task.get("status", "")).upper() not in {"PENDING", "IN_PROGRESS"}:
            continue
        outcome, reason = receipt_outcome(task)
        if outcome is None:
            continue
        task["status"] = outcome
        task["completed_at"] = now()
        if reason:
            task["blocker"] = reason
        receipt = task.get("receipt")
        if isinstance(receipt, str) and (ROOT / receipt).is_file():
            task["receipt_sha"] = blob_sha([(ROOT / receipt)].bad) if False else blob_sha((ROOT / receipt).read_bytes())
            task["receipt_sha_type"] = "git_blob"
        reconciled.append(str(task.get("id", "")))
        changed = True

    current_id = queue.get("current_task")
    current = by_id.get(current_id) if isinstance(current_id, str) else None
    if current and str(current.get("status", "")).upper() == "IN_PROGRESS":
        if changed:
            queue["updated_at"] = now()
            save_if_changed(QUEUE, queue, before)
        result = {
            "action": "stop",
            "reason": "active_task_in_progress",
            "task_id": current_id,
            "queue_changed": changed,
            "reconciled": reconciled,
        }
        dispatch_out.write_bytes(dump(result))
        return result

    selected = select_task(tasks, by_id, force_task_id)
    if selected is None:
        statuses = [str(t.get("status", "")).upper() for t in tasks if isinstance(t, dict)]
        wanted = "BLOCKED" if any(s.startswith("BLOCKED") for s in statuses) else "IDLE"
        if queue.get("queue_state") != wanted:
            queue["queue_state"] = wanted
            changed = True
        if changed:
            queue["updated_at"] = now()
            save_if_changed(QUEUE, queue, before)
        result = {
            "action": "stop",
            "reason": "no_eligible_pending_task",
            "queue_changed": changed,
            "reconciled": reconciled,
        }
        dispatch_out.write_bytes(dump(result))
        return result

    task_id = selected.get("id")
    if not isinstance(task_id, str) or not task_id:
        raise ValueError("selected task has no id")
    trace_id = (
        f"{trace_prefix}_{task_id.lower().replace('-', '_')}_"
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    )
    workflow_id, inputs = dispatch_binding(selected, task_id, trace_id)
    selected.update(status="IN_PROGRESS", started_at=now(), trace_id=trace_id)
    queue.update(current_task=task_id, queue_state="ACTIVE", updated_at=now())
    append_dispatch_log({
        "dispatched_at": now(), "task_id": task_id, "workflow_id": workflow_id,
        "trace_id": trace_id, "http_status": None, "completion_claimed": False,
        "source": "roadmap_autopilot_universal",
    })
    changed = True
    save_if_changed(QUEUE, queue, before)
    result = {
        "action": "dispatch", "task_id": task_id, "trace_id": trace_id,
        "workflow_id": workflow_id, "inputs": inputs,
        "queue_changed": changed, "reconciled": reconciled,
    }
    dispatch_out.write_bytes(dump(result))
    return result

def cli() -> None:
    parser = argparse.ArgumentParser(description="Universal queue-driven roadmap autopilot")
    parser.add_argument("--force-task-id", default="")
    parser.add_argument("--trace-prefix", default="autopilot")
    parser.add_argument("--dispatch-out", required=True)
    args = parser.parse_args()
    result = main(args.force_task_id.strip(), args.trace_prefix.strip() or "autopilot", Path(args.dispatch_out))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))

if __name__ == "__main__":
    cli()
