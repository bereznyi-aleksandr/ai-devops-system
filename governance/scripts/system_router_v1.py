#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "governance" / "PROTOCOL.md"
INDEX = ROOT / "governance" / "runtime" / "tasks" / "index.json"
TASKS = ROOT / "governance" / "runtime" / "tasks"
NOTIFICATIONS = ROOT / "governance" / "runtime" / "notifications"
EXECUTOR_PACKET = ROOT / "governance" / "runtime" / "packets" / "executor_packet_current.json"
AUDITOR_PACKET = ROOT / "governance" / "runtime" / "packets" / "auditor_packet_current.json"


class RouterError(RuntimeError):
    pass


def read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise RouterError(f"Missing required file: {path.relative_to(ROOT)}") from e
    except json.JSONDecodeError as e:
        raise RouterError(f"Invalid JSON in {path.relative_to(ROOT)}: {e}") from e


def protocol_version() -> str:
    text = PROTOCOL.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped.startswith("Версия:"):
            value = stripped.split(":", 1)[1].strip()
            match = re.search(r"v\d+\.\d+(?:-[A-Z0-9]+)?", value)
            return match.group(0) if match else value.split()[0]
    raise RouterError("Could not determine protocol version from governance/PROTOCOL.md")


def registry_path(registry_path_value: str, task_id: str) -> Path:
    if registry_path_value:
        path = ROOT / registry_path_value
        if path.exists():
            return path
    return TASKS / f"{task_id}.json"


def latest_notification() -> Tuple[Dict[str, Any], str] | None:
    found = []
    for role_dir in (NOTIFICATIONS / "executor", NOTIFICATIONS / "auditor"):
        if not role_dir.exists():
            continue
        for path in role_dir.glob("*.notify.json"):
            try:
                note = read_json(path)
                note["_notification_path"] = str(path.relative_to(ROOT))
                found.append((path.stat().st_mtime, note))
            except Exception:
                continue
    found.sort(key=lambda row: row[0], reverse=True)
    for _, note in found:
        task_id = str(note.get("task_id", "")).strip()
        if not task_id:
            continue
        path = registry_path(str(note.get("registry_path", "")).strip(), task_id)
        if path.exists():
            return note, str(path.relative_to(ROOT))
    return None


def index_task() -> Tuple[Dict[str, Any], str]:
    index = read_json(INDEX)
    items = index.get("items")
    if not isinstance(items, list):
        raise RouterError("Task index has no items list")
    for role, bucket in (("EXECUTOR", "AWAITING_EXECUTOR"), ("AUDITOR", "AWAITING_AUDITOR")):
        for item in items:
            if not isinstance(item, dict):
                continue
            item_role = str(item.get("next_role", "")).strip().upper()
            item_bucket = str(item.get("status_bucket", "")).strip().upper()
            if item_role != role and item_bucket != bucket:
                continue
            task_id = str(item.get("task_id", "")).strip()
            if not task_id:
                continue
            path = registry_path(str(item.get("registry_path", "")).strip(), task_id)
            return {
                "task_id": task_id,
                "role": role,
                "notify_role": role,
                "next_action": item.get("next_action", ""),
                "current_state": item.get("current_state", ""),
                "status_bucket": item.get("status_bucket", ""),
                "registry_path": str(path.relative_to(ROOT)),
                "_source": "index_fallback",
            }, str(path.relative_to(ROOT))
    raise RouterError("No AWAITING_EXECUTOR/AWAITING_AUDITOR task found in index")


def active_context() -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    selected = latest_notification()
    note, path_rel = selected if selected else index_task()
    task = read_json(ROOT / path_rel)
    return task, note, path_rel


def normalized(task: Dict[str, Any], note: Dict[str, Any], path_rel: str, proto: str) -> Dict[str, str]:
    task_id = str(task.get("task_id") or note.get("task_id") or "").strip()
    state = str(task.get("current_state") or note.get("current_state") or "").strip()
    role = str(task.get("next_role") or note.get("role") or note.get("notify_role") or "").strip().upper()
    action = str(task.get("next_action") or note.get("next_action") or "").strip()
    if not task_id:
        raise RouterError("Selected task has no task_id")
    if role not in {"EXECUTOR", "AUDITOR"}:
        raise RouterError(f"Unsupported next_role: {role}")
    if not action:
        raise RouterError(f"Task {task_id} has no next_action")
    event_id = f"ROUTER:{task_id}:{state or 'UNKNOWN'}"
    return {
        "protocol_version": proto,
        "event_id": event_id,
        "parent_event_id": str(task.get("last_event_id") or event_id),
        "task_id": task_id,
        "event_type": str(task.get("last_event_type") or state),
        "summary": str(task.get("last_summary") or task.get("title") or ""),
        "state": state,
        "status_bucket": str(task.get("status_bucket") or note.get("status_bucket") or ""),
        "next_role": role,
        "next_action": action,
        "artifact_ref": str(task.get("artifact_ref") or task.get("latest_artifact_ref") or ""),
        "proof_ref": str(task.get("proof_ref") or task.get("latest_proof_ref") or ""),
        "ci_ref": str(task.get("ci_ref") or task.get("latest_ci_ref") or ""),
        "log_ref": str(task.get("log_ref") or task.get("latest_log_ref") or ""),
        "commit_sha": str(task.get("commit_sha") or task.get("latest_commit_sha") or ""),
        "latest_result_manifest": str(task.get("latest_result_manifest") or ""),
        "registry_path": path_rel,
        "notification_path": str(note.get("_notification_path", "")),
    }


def packet_plan(n: Dict[str, str]) -> Dict[str, Any]:
    base = {
        "protocol_version": n["protocol_version"],
        "runtime": "GitHub Actions",
        "role": n["next_role"],
        "input_event_id": n["event_id"],
        "parent_event_id": n["parent_event_id"],
        "task_id": n["task_id"],
        "registry_path": n["registry_path"],
        "notification_path": n["notification_path"],
        "current_state": n["state"],
        "status_bucket": n["status_bucket"],
        "next_role": n["next_role"],
        "next_action": n["next_action"],
        "artifact_ref": n["artifact_ref"],
        "proof_ref": n["proof_ref"],
        "ci_ref": n["ci_ref"],
        "log_ref": n["log_ref"],
        "latest_result_manifest": n["latest_result_manifest"],
        "summary": f"SYSTEM router generated {n['next_role']} packet for {n['task_id']} / {n['next_action']}.",
        "constraints": ["Do not write governance/exchange_ledger.csv", "Do not merge"],
    }
    if n["next_role"] == "EXECUTOR":
        base["task_instruction"] = "Create governance/proofs/TASK-CODEX-001-proof.txt with content: AUTONOMOUS EXECUTION CONFIRMED"
        base["constraints"] += ["Write only allowed task artifacts", "Write executor_materialize_result.json"]
        return {"packet_path": str(EXECUTOR_PACKET.relative_to(ROOT)), "role": "EXECUTOR", "packet": base}
    base["decision_id"] = f"AUDIT-{n['task_id']}-AUTO-0001"
    base["reviewed_ref"] = n["artifact_ref"]
    base["reviewed_commit_sha"] = n["commit_sha"]
    base["constraints"] += ["Do not implement product changes", "Write auditor_materialize_result.json"]
    return {"packet_path": str(AUDITOR_PACKET.relative_to(ROOT)), "role": "AUDITOR", "packet": base}


def main() -> int:
    try:
        proto = protocol_version()
        task, note, path_rel = active_context()
        n = normalized(task, note, path_rel, proto)
        plan = packet_plan(n)
        print(json.dumps({
            "system_router_version": "v2-runtime-registry",
            "source_of_truth": "runtime_task_registry",
            "protocol_version": proto,
            "index_path": str(INDEX.relative_to(ROOT)),
            "registry_path": n["registry_path"],
            "notification_path": n["notification_path"],
            "current_event_id": n["event_id"],
            "current_task_id": n["task_id"],
            "current_state": n["state"],
            "current_event_type": n["event_type"],
            "next_role": n["next_role"],
            "next_action": n["next_action"],
            "artifact_ref": n["artifact_ref"],
            "suggested_packet_path": plan["packet_path"],
            "suggested_packet": plan["packet"],
        }, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"system_router_version": "v2-runtime-registry", "result": "BLOCKED", "error": str(e)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
