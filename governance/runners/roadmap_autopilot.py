#!/usr/bin/env python3
"""Universal queue-driven roadmap dispatcher; no task-ID allowlist."""
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "governance/roadmap/ACTIVE_QUEUE.json"
LOG = ROOT / "governance/state/dispatch_executed.jsonl"
DONE = {"DONE", "DONE_LIMITED_SCOPE", "SKIPPED_BY_OPERATOR"}
NONTERMINAL = {"PENDING", "IN_PROGRESS"}
PASS = {"PASS", "DONE"}
BLOCK = {"BLOCKED", "FAIL", "FAILED", "ERROR"}

def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def dump(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()

def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def load(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value

def outcome(task):
    ref = task.get("receipt")
    if not isinstance(ref, str) or not ref:
        return None, None
    path = (ROOT / ref).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError:
        return "BLOCKED", "receipt_path_outside_repository"
    if not path.is_file():
        return None, None
    try:
        state = str(load(path).get("status", "")).upper()
    except Exception:
        return "BLOCKED", "unreadable_receipt"
    if state in PASS:
        return "DONE", None
    if state in BLOCK:
        return "BLOCKED", f"receipt_status_{state.lower()}"
    return None, None

def deps_ok(task, by_id):
    deps = task.get("depends_on", [])
    return isinstance(deps, list) and all(
        isinstance(dep, str) and dep in by_id and str(by_id[dep].get("status", "")).upper() in DONE
        for dep in deps
    )

def dispatch_binding(task, task_id, trace_id):
    execution = task.get("execution")
    if isinstance(execution, dict) and str(execution.get("kind", "")).lower() == "workflow":
        workflow_id = execution.get("workflow_id")
        inputs = execution.get("inputs", {})
        if not isinstance(workflow_id, str) or not workflow_id or workflow_id.startswith("/") or ".." in Path(workflow_id).parts:
            raise ValueError("workflow execution requires repository-relative workflow_id")
        if not isinstance(inputs, dict):
            raise ValueError("workflow execution inputs must be an object")
        render = lambda v: str(v).replace("${task_id}", task_id).replace("${trace_id}", trace_id)
        return workflow_id, {str(k): render(v) for k, v in inputs.items()}
    return "roadmap-task-executor.yml", {"task_id": task_id, "trace_id": trace_id}

def main(force, prefix, dispatch_out):
    before = QUEUE.read_bytes()
    queue = load(QUEUE)
    tasks = queue.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("ACTIVE_QUEUE.tasks must be a list")
    by_id = {t["id"]: t for t in tasks if isinstance(t, dict) and isinstance(t.get("id"), str)}
    changed, reconciled = False, []
    for task in tasks:
        if not isinstance(task, dict) or str(task.get("status", "")).upper() not in NONTERMINAL:
            continue
        state, reason = outcome(task)
        if not state:
            continue
        task["status"], task["completed_at"] = state, now()
        if reason:
            task["blocker"] = reason
        ref = task.get("receipt")
        if isinstance(ref, str) and (ROOT / ref).is_file():
            task["receipt_sha"], task["receipt_sha_type"] = blob((ROOT / ref).read_bytes()), "git_blob"
        changed, reconciled = True, reconciled + [task["id"]]

    active = by_id.get(queue.get("current_task"))
    if active and str(active.get("status", "")).upper() == "IN_PROGRESS":
        result = {"action": "stop", "reason": "active_task_in_progress", "task_id": active["id"], "queue_changed": changed, "reconciled": reconciled}
    else:
        selected = by_id.get(force) if force else next(
            (t for t in tasks if isinstance(t, dict) and str(t.get("status", "")).upper() == "PENDING" and deps_ok(t, by_id)),
            None,
        )
        if force and (selected is None or str(selected.get("status", "")).upper() != "PENDING" or not deps_ok(selected, by_id)):
            raise ValueError(f"forced task is not eligible: {force}")
        if not selected:
            states = [str(t.get("status", "")).upper() for t in tasks if isinstance(t, dict)]
            desired = "BLOCKED" if any(s.startswith("BLOCKED") for s in states) else "IDLE"
            if "IN_PROGRESS" not in states and queue.get("queue_state") != desired:
                queue["queue_state"], changed = desired, True
            result = {"action": "stop", "reason": "no_eligible_pending_task", "queue_changed": changed, "reconciled": reconciled}
        else:
            task_id = selected["id"]
            trace_id = f"{prefix}_{task_id.lower().replace('-', '_')}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
            workflow_id, inputs = dispatch_binding(selected, task_id, trace_id)
            selected.update(status="IN_PROGRESS", started_at=now(), trace_id=trace_id)
            queue.update(current_task=task_id, queue_state="ACTIVE")
            changed = True
            LOG.parent.mkdir(parents=True, exist_ok=True)
            with LOG.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"dispatched_at": now(), "task_id": task_id, "workflow_id": workflow_id, "trace_id": trace_id, "http_status": None, "completion_claimed": False, "source": "roadmap_autopilot_universal"}, sort_keys=True) + "\n")
            result = {"action": "dispatch", "task_id": task_id, "trace_id": trace_id, "workflow_id": workflow_id, "inputs": inputs, "queue_changed": changed, "reconciled": reconciled}

    if changed:
        queue["updated_at"] = now()
        QUEUE.write_bytes(dump(queue))
    dispatch_out.write_bytes(dump(result))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-task-id", default="")
    parser.add_argument("--trace-prefix", default="autopilot")
    parser.add_argument("--dispatch-out", required=True)
    args = parser.parse_args()
    main(args.force_task_id.strip(), args.trace_prefix.strip() or "autopilot", Path(args.dispatch_out))
