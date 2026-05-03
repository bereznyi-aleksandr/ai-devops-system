#!/usr/bin/env python3
import argparse
import json
import os
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
SEQUENCE_PATH = ROOT / "governance/policies/role_sequence.json"
STATE_PATH = ROOT / "governance/state/role_cycle_state.json"
EVENT_LOG = ROOT / "governance/events/role_orchestrator.jsonl"
ROUTING_PATH = ROOT / "governance/state/routing.json"
PROVIDER_STATUS_PATH = ROOT / "governance/state/provider_status.json"

ROLE_WORKFLOW = "gpt-hosted-roles.yml"
MAIN_ISSUE = "31"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path, default=None):
    p = Path(path)
    if not p.exists() or not p.read_text(encoding="utf-8").strip():
        return default if default is not None else {}
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_event(entry):
    EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry["timestamp"] = entry.get("timestamp") or now_iso()
    with EVENT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def github_api(method, url, payload=None):
    token = os.environ.get("AI_SYSTEM_GITHUB_PAT") or os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("AI_SYSTEM_GITHUB_PAT/GH_TOKEN is missing")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "ai-devops-role-orchestrator"
        }
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw else {"status": resp.status}


def post_issue_comment(body):
    repo = os.environ.get("GITHUB_REPOSITORY", "bereznyi-aleksandr/ai-devops-system")
    issue = os.environ.get("MAIN_ISSUE", MAIN_ISSUE)
    return github_api(
        "POST",
        f"https://api.github.com/repos/{repo}/issues/{issue}/comments",
        {"body": body}
    )


def dispatch_workflow(workflow_file, inputs):
    repo = os.environ.get("GITHUB_REPOSITORY", "bereznyi-aleksandr/ai-devops-system")
    return github_api(
        "POST",
        f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_file}/dispatches",
        {
            "ref": os.environ.get("GITHUB_REF_NAME", "main"),
            "inputs": inputs
        }
    )


def select_provider(role):
    routing = load_json(ROUTING_PATH, {})
    provider_status = load_json(PROVIDER_STATUS_PATH, {"providers": {}})
    role_cfg = routing.get("roles", {}).get(role, {})
    provider = role_cfg.get("active", "claude")
    provider_state = provider_status.get("providers", {}).get(provider, {})

    if provider == "claude" and provider_state.get("status") in ("limited", "error"):
        provider = role_cfg.get("reserve", "gpt") or "gpt"

    return provider


def next_role_for_cycle(sequence, current_index):
    next_index = current_index + 1
    if next_index >= len(sequence):
        return None, next_index
    return sequence[next_index], next_index


def start_cycle(task_type, task, trace_id=None, cycle_id=None):
    seq_policy = load_json(SEQUENCE_PATH, {})
    state = load_json(STATE_PATH, {"version": 1, "cycles": {}})

    task_type = task_type or seq_policy.get("default_task_type", "default_development")
    sequence = seq_policy.get("task_types", {}).get(task_type)
    if not sequence:
        raise RuntimeError(f"Unknown task_type or empty sequence: {task_type}")

    cycle_id = cycle_id or ("cyc_" + uuid.uuid4().hex[:16])
    trace_id = trace_id or ("fsm_" + uuid.uuid4().hex[:16])

    role, index = next_role_for_cycle(sequence, -1)
    provider = select_provider(role)

    cycles = state.setdefault("cycles", {})
    cycles[cycle_id] = {
        "cycle_id": cycle_id,
        "trace_id": trace_id,
        "task_type": task_type,
        "sequence": sequence,
        "current_index": index,
        "current_role": role,
        "status": "role_dispatched",
        "task": task,
        "updated_at": now_iso()
    }
    state["updated_at"] = now_iso()
    state["last_cycle_id"] = cycle_id
    state["last_trace_id"] = trace_id
    state["status"] = "cycle_started"
    write_json(STATE_PATH, state)

    dispatch_role(cycle_id, trace_id, task_type, role, provider, task)
    append_event({
        "event": "ROLE_CYCLE_STARTED",
        "cycle_id": cycle_id,
        "trace_id": trace_id,
        "task_type": task_type,
        "role": role,
        "provider": provider
    })
    return cycle_id, trace_id, role, provider


def advance_cycle(cycle_id, role, status, note=""):
    state = load_json(STATE_PATH, {"version": 1, "cycles": {}})
    cycles = state.setdefault("cycles", {})
    cycle = cycles.get(cycle_id)
    if not cycle:
        raise RuntimeError(f"Unknown cycle_id: {cycle_id}")

    append_event({
        "event": "ROLE_RESULT_RECEIVED",
        "cycle_id": cycle_id,
        "trace_id": cycle.get("trace_id"),
        "role": role,
        "status": status,
        "note": note[:1000]
    })

    if status not in ("ROLE_DONE", "APPROVED"):
        cycle["status"] = "blocked"
        cycle["blocker"] = {"role": role, "status": status, "note": note}
        cycle["updated_at"] = now_iso()
        write_json(STATE_PATH, state)
        post_issue_comment(
            "BEM-ROLE-ORCHESTRATOR | BLOCKED\n\n"
            f"Cycle: {cycle_id}\n"
            f"Trace: {cycle.get('trace_id')}\n"
            f"Role: {role}\n"
            f"Status: {status}\n"
            f"Note: {note[:1500]}"
        )
        return None, None

    sequence = cycle.get("sequence", [])
    next_role, next_index = next_role_for_cycle(sequence, int(cycle.get("current_index", -1)))
    if not next_role:
        cycle["status"] = "completed"
        cycle["current_index"] = next_index
        cycle["current_role"] = None
        cycle["updated_at"] = now_iso()
        write_json(STATE_PATH, state)
        append_event({
            "event": "ROLE_CYCLE_COMPLETED",
            "cycle_id": cycle_id,
            "trace_id": cycle.get("trace_id")
        })
        post_issue_comment(
            "BEM-ROLE-ORCHESTRATOR | CYCLE COMPLETED\n\n"
            f"Cycle: {cycle_id}\n"
            f"Trace: {cycle.get('trace_id')}\n"
            f"Task type: {cycle.get('task_type')}\n"
            "Status: completed"
        )
        return None, None

    provider = select_provider(next_role)
    cycle["current_index"] = next_index
    cycle["current_role"] = next_role
    cycle["status"] = "role_dispatched"
    cycle["updated_at"] = now_iso()
    write_json(STATE_PATH, state)

    dispatch_role(
        cycle_id,
        cycle.get("trace_id"),
        cycle.get("task_type"),
        next_role,
        provider,
        cycle.get("task", "")
    )
    append_event({
        "event": "ROLE_DISPATCHED",
        "cycle_id": cycle_id,
        "trace_id": cycle.get("trace_id"),
        "role": next_role,
        "provider": provider
    })
    return next_role, provider


def dispatch_role(cycle_id, trace_id, task_type, role, provider, task):
    if role == "curator_summary":
        post_issue_comment(
            "BEM-ROLE-ORCHESTRATOR | CURATOR SUMMARY STEP\n\n"
            f"Cycle: {cycle_id}\n"
            f"Trace: {trace_id}\n"
            f"Task type: {task_type}\n"
            "Next: curator summary/report only."
        )
        return

    dispatch_workflow(ROLE_WORKFLOW, {
        "role": role,
        "provider": provider,
        "trace_id": trace_id,
        "cycle_id": cycle_id,
        "task_type": task_type,
        "task": task[:4000]
    })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["start", "advance"], required=True)
    parser.add_argument("--task-type", default="default_development")
    parser.add_argument("--task", default="")
    parser.add_argument("--trace-id", default="")
    parser.add_argument("--cycle-id", default="")
    parser.add_argument("--role", default="")
    parser.add_argument("--status", default="ROLE_DONE")
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    append_event({"event": "ROLE_ORCHESTRATOR_START", "mode": args.mode})

    if args.mode == "start":
        cycle_id, trace_id, role, provider = start_cycle(
            task_type=args.task_type,
            task=args.task,
            trace_id=args.trace_id or None,
            cycle_id=args.cycle_id or None
        )
        print("BEM-ROLE-ORCHESTRATOR | STARTED")
        print("CYCLE_ID=" + cycle_id)
        print("TRACE_ID=" + trace_id)
        print("ROLE=" + role)
        print("PROVIDER=" + provider)
        return 0

    next_role, provider = advance_cycle(
        cycle_id=args.cycle_id,
        role=args.role,
        status=args.status,
        note=args.note
    )
    print("BEM-ROLE-ORCHESTRATOR | ADVANCED")
    print("NEXT_ROLE=" + str(next_role or "none"))
    print("PROVIDER=" + str(provider or "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
