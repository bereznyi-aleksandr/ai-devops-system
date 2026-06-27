#!/usr/bin/env python3
"""Generic executor for a declared roadmap task; no task-ID allowlist."""
import argparse, hashlib, json, re, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "governance/roadmap/ACTIVE_QUEUE.json"
LOG = ROOT / "governance/logs/execution_log.jsonl"
PROOFS = ROOT / "governance/proofs"
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

def receipt_state(task):
    ref = task.get("receipt")
    if not isinstance(ref, str) or not ref:
        return "BLOCKED", {"error": "missing_task_receipt"}
    path = (ROOT / ref).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError:
        return "BLOCKED", {"error": "receipt_path_outside_repository"}
    if not path.is_file():
        return "BLOCKED", {"error": "missing_task_receipt", "receipt": ref}
    try:
        status = str(load(path).get("status", "")).upper()
    except Exception:
        return "BLOCKED", {"error": "unreadable_task_receipt", "receipt": ref}
    return ("PASS" if status in PASS else "BLOCKED"), {"receipt": ref, "receipt_status": status}

def execute(task):
    execution = task.get("execution")
    if not isinstance(execution, dict):
        return "BLOCKED", {"error": "missing_execution_binding"}
    kind = str(execution.get("kind", "python")).lower()
    if kind == "receipt_only":
        return receipt_state(task)
    if kind != "python":
        return "BLOCKED", {"error": f"unsupported_execution_kind:{kind}"}
    entry = execution.get("entrypoint")
    if not isinstance(entry, str) or not entry:
        return "BLOCKED", {"error": "python_execution_requires_entrypoint"}
    path = (ROOT / entry).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError:
        return "BLOCKED", {"error": "entrypoint_outside_repository", "entrypoint": entry}
    if not path.is_file() or path.suffix != ".py":
        return "BLOCKED", {"error": "missing_python_entrypoint", "entrypoint": entry}
    args = execution.get("args", [])
    if not isinstance(args, list) or not all(isinstance(arg, (str, int, float)) for arg in args):
        return "BLOCKED", {"error": "python_execution_args_must_be_scalar_list"}
    try:
        timeout = max(1, min(int(execution.get("timeout_seconds", 900)), 3600))
    except (TypeError, ValueError):
        return "BLOCKED", {"error": "invalid_timeout_seconds"}
    try:
        run = subprocess.run([sys.executable, str(path), *map(str, args)], cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        return "BLOCKED", {"error": "python_execution_timeout", "entrypoint": entry, "timeout_seconds": timeout, "stdout_tail": (exc.stdout or "")[-4000:], "stderr_tail": (exc.stderr or "")[-4000:]}
    except OSError as exc:
        return "BLOCKED", {"error": f"python_execution_oserror:{type(exc).__name__}", "entrypoint": entry}
    return ("PASS" if run.returncode == 0 else "BLOCKED"), {"entrypoint": entry, "args": list(map(str, args)), "returncode": run.returncode, "timeout_seconds": timeout, "stdout_tail": run.stdout[-4000:], "stderr_tail": run.stderr[-4000:]}

def main(task_id, trace_id):
    queue = load(QUEUE)
    tasks = queue.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("ACTIVE_QUEUE.tasks must be a list")
    task = next((t for t in tasks if isinstance(t, dict) and t.get("id") == task_id), None)
    if task is None:
        raise ValueError(f"unknown task: {task_id}")
    if str(task.get("status", "")).upper() != "IN_PROGRESS":
        raise ValueError(f"task is not IN_PROGRESS: {task_id}")
    status, details = execute(task)
    receipt = {"schema_version": 1, "task_id": task_id, "trace_id": trace_id, "created_at": now(), "status": status, "evidence_kind": "runtime_task_executor", "execution": details}
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", task_id).strip("_") or "task"
    receipt_path = PROOFS / f"{name}_executor_receipt.json"
    receipt_data = dump(receipt)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_bytes(receipt_data)
    task.update(
        status="DONE" if status == "PASS" else "BLOCKED",
        completed_at=now(),
        receipt=str(receipt_path.relative_to(ROOT)),
        receipt_sha=blob(receipt_data),
        receipt_sha_type="git_blob",
    )
    if status != "PASS":
        task["blocker"] = details.get("error", "task_execution_blocked")
    else:
        task.pop("blocker", None)
    if queue.get("current_task") == task_id:
        queue["current_task"] = None
    queue.update(queue_state="PENDING" if status == "PASS" else "BLOCKED", updated_at=now())
    QUEUE.write_bytes(dump(queue))
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"timestamp": now(), "task_id": task_id, "trace_id": trace_id, "status": task["status"].lower(), "receipt": task["receipt"], "source": "roadmap_task_executor"}, sort_keys=True) + "\n")
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--trace-id", required=True)
    args = parser.parse_args()
    main(args.task_id, args.trace_id)
