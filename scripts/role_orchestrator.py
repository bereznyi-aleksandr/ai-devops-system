#!/usr/bin/env python3
import argparse
import json
import os
import urllib.request
import uuid

try:
    import provider_failover as provider_failover_layer
except Exception:
    provider_failover_layer = None

from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
SEQUENCE_PATH = ROOT / "governance/policies/role_sequence.json"
STATE_PATH = ROOT / "governance/state/role_cycle_state.json"
EVENT_LOG = ROOT / "governance/events/role_orchestrator.jsonl"
ROUTING_PATH = ROOT / "governance/state/routing.json"
PROVIDER_STATUS_PATH = ROOT / "governance/state/provider_status.json"
PROVIDER_ADAPTERS_PATH = ROOT / "governance/policies/provider_adapters.json"
PROVIDER_ADAPTER_LOG = ROOT / "governance/events/provider_adapter.jsonl"
EMERGENCY_STOP_PATH = ROOT / "governance/state/emergency_stop.json"

ROLE_WORKFLOW = "gpt-hosted-roles.yml"
MAIN_ISSUE = "31"
TERMINAL_REPORT_ROLES = {"curator_summary"}
DEFAULT_ACTIVE_STATUSES = {"cycle_started", "role_dispatched"}
DEFAULT_TERMINAL_STATUSES = {"completed", "blocked", "abandoned_stale_test", "stale_timeout", "step_limit_exceeded"}
RUNNER_BACKED_PROVIDERS = {"gpt_codex", "codex"}
UNHEALTHY_FAILURE_TYPES = {"provider_limit", "api_error", "runner_unavailable"}


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


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


def append_provider_adapter_event(entry):
    PROVIDER_ADAPTER_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry["timestamp"] = entry.get("timestamp") or now_iso()
    with PROVIDER_ADAPTER_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def provider_failover_candidate(role, trace_id="", task_type="role_orchestrator"):
    if provider_failover_layer is None:
        append_provider_adapter_event({
            "event": "PROVIDER_FAILOVER_LAYER_UNAVAILABLE",
            "role": role,
            "reason": "import_failed_or_disabled"
        })
        return None
    try:
        result = provider_failover_layer.select_provider(
            role,
            trace_id=trace_id,
            task_type=task_type
        )
    except Exception as exc:
        append_provider_adapter_event({
            "event": "PROVIDER_FAILOVER_LAYER_ERROR",
            "role": role,
            "error": str(exc)[:500]
        })
        return None
    if result.get("status") == "ok" and result.get("provider"):
        append_provider_adapter_event({
            "event": "PROVIDER_FAILOVER_CANDIDATE",
            "role": role,
            "provider": result.get("provider"),
            "fallback_used": result.get("fallback_used"),
            "trace_id": result.get("trace_id"),
            "task_type": result.get("task_type")
        })
        return result.get("provider")
    append_provider_adapter_event({
        "event": "PROVIDER_FAILOVER_NO_CANDIDATE",
        "role": role,
        "status": result.get("status"),
        "reason": result.get("reason")
    })
    return None


def emergency_stop_blocked(mode, trace_id="", cycle_id=""):
    state = load_json(EMERGENCY_STOP_PATH, {"enabled": False})
    if not state.get("enabled"):
        return False

    reason = state.get("reason") or "emergency stop enabled"
    event = {
        "event": "ROLE_ORCHESTRATOR_EMERGENCY_STOP_BLOCKED",
        "mode": mode,
        "trace_id": trace_id or state.get("trace_id"),
        "cycle_id": cycle_id,
        "reason": reason,
        "emergency_stop_updated_at": state.get("updated_at"),
        "emergency_stop_updated_by": state.get("updated_by")
    }
    append_event(event)

    print("BEM-ROLE-ORCHESTRATOR | EMERGENCY_STOP_BLOCKED")
    print("MODE=" + str(mode))
    print("TRACE_ID=" + str(event.get("trace_id") or ""))
    print("CYCLE_ID=" + str(cycle_id or ""))
    print("REASON=" + str(reason))

    try:
        post_issue_comment(
            "BEM-ROLE-ORCHESTRATOR | EMERGENCY STOP BLOCKED\n\n"
            f"Mode: {mode}\n"
            f"Trace: {event.get('trace_id')}\n"
            f"Cycle: {cycle_id or 'none'}\n"
            f"Reason: {reason}\n\n"
            "Status: no role dispatch was performed."
        )
    except Exception as exc:
        append_event({
            "event": "ROLE_ORCHESTRATOR_EMERGENCY_STOP_REPORT_FAILED",
            "mode": mode,
            "trace_id": event.get("trace_id"),
            "cycle_id": cycle_id,
            "error": str(exc)[:500]
        })

    return True


def load_provider_adapters():
    return load_json(PROVIDER_ADAPTERS_PATH, {
        "default_provider": "gpt",
        "adapters": {
            "gpt": {
                "enabled": True,
                "mode": "workflow_dispatch",
                "workflow": "gpt-hosted-roles.yml",
                "supports_roles": ["analyst", "auditor", "executor", "curator"]
            }
        }
    })


def cycle_controls(seq_policy):
    controls = seq_policy.get("cycle_controls", {})
    return {
        "max_cycle_age_minutes": int(controls.get("max_cycle_age_minutes", 30)),
        "max_role_steps_per_cycle": int(controls.get("max_role_steps_per_cycle", 8)),
        "active_statuses": set(controls.get("active_statuses") or DEFAULT_ACTIVE_STATUSES),
        "terminal_statuses": set(controls.get("terminal_statuses") or DEFAULT_TERMINAL_STATUSES),
        "runner_backed_providers": set(controls.get("runner_backed_providers") or RUNNER_BACKED_PROVIDERS),
        "step_limit_status": controls.get("step_limit_status", "step_limit_exceeded")
    }


def update_provider_status(provider, status, failure_type=None, reason=None, role=None, cycle_id=None, trace_id=None):
    if not provider:
        return
    now_text = now_iso()
    state = load_json(PROVIDER_STATUS_PATH, {"version": 1, "providers": {}})
    state.setdefault("providers", {})
    item = state["providers"].setdefault(provider, {})
    item["status"] = status
    item["updated_at"] = now_text
    if status in ("error", "limited"):
        item["last_failure_at"] = now_text
        item["last_failure_type"] = failure_type or status
        item["last_error_excerpt"] = reason or ""
        item["failure_count"] = int(item.get("failure_count") or 0) + 1
    if role:
        item["last_role"] = role
    if cycle_id:
        item["last_cycle_id"] = cycle_id
    if trace_id:
        item["last_trace_id"] = trace_id
    state["updated_at"] = now_text
    write_json(PROVIDER_STATUS_PATH, state)


def post_blocker_report(cycle_id, cycle, role, provider, reason, failure_type):
    post_issue_comment(
        "BEM-ROLE-ORCHESTRATOR | BLOCKED\n\n"
        f"Cycle: {cycle_id}\n"
        f"Trace: {cycle.get('trace_id')}\n"
        f"Task type: {cycle.get('task_type')}\n"
        f"Role: {role}\n"
        f"Provider: {provider}\n"
        f"Failure type: {failure_type}\n"
        f"Status: blocked\n"
        f"Reason: {reason}"
    )


def post_step_limit_report(cycle_id, cycle, max_steps):
    post_issue_comment(
        "BEM-ROLE-ORCHESTRATOR | STEP LIMIT EXCEEDED\n\n"
        f"Cycle: {cycle_id}\n"
        f"Trace: {cycle.get('trace_id')}\n"
        f"Task type: {cycle.get('task_type')}\n"
        f"Current role: {cycle.get('current_role')}\n"
        f"Current provider: {cycle.get('current_provider')}\n"
        f"Step count: {cycle.get('step_count')}\n"
        f"Max role steps: {max_steps}\n"
        "Status: step_limit_exceeded\n"
        "Reason: role FSM exceeded configured max_role_steps_per_cycle; next dispatch blocked."
    )


def mark_step_limit_exceeded(state, cycle_id, cycle, max_steps, reason, post_report=False):
    now_text = now_iso()
    cycle["previous_status"] = cycle.get("status")
    cycle["status"] = "step_limit_exceeded"
    cycle["blocked_at"] = now_text
    cycle["step_limit"] = {
        "max_role_steps_per_cycle": max_steps,
        "step_count": cycle.get("step_count", 0),
        "reason": reason
    }
    cycle["updated_at"] = now_text
    state["updated_at"] = now_text
    state["status"] = "step_limit_exceeded"
    append_event({
        "event": "ROLE_CYCLE_STEP_LIMIT_EXCEEDED",
        "cycle_id": cycle_id,
        "trace_id": cycle.get("trace_id"),
        "role": cycle.get("current_role"),
        "provider": cycle.get("current_provider"),
        "step_count": cycle.get("step_count", 0),
        "max_role_steps_per_cycle": max_steps,
        "reason": reason
    })
    write_json(STATE_PATH, state)
    if post_report:
        post_step_limit_report(cycle_id, cycle, max_steps)


def register_role_step(state, cycle_id, cycle, step_type, role, provider=None, post_report=False):
    seq_policy = load_json(SEQUENCE_PATH, {})
    max_steps = cycle_controls(seq_policy)["max_role_steps_per_cycle"]
    now_text = now_iso()
    cycle["step_count"] = int(cycle.get("step_count") or 0) + 1
    history = cycle.setdefault("step_history", [])
    history.append({
        "step": cycle["step_count"],
        "type": step_type,
        "role": role,
        "provider": provider,
        "timestamp": now_text
    })
    cycle["step_history"] = history[-50:]
    if cycle["step_count"] > max_steps:
        mark_step_limit_exceeded(
            state,
            cycle_id,
            cycle,
            max_steps,
            f"{step_type} would exceed max_role_steps_per_cycle",
            post_report=post_report
        )
        return False
    return True


def mark_stale_cycles(state, seq_policy, post_reports=False):
    controls = cycle_controls(seq_policy)
    max_age_minutes = controls["max_cycle_age_minutes"]
    active_statuses = controls["active_statuses"]
    terminal_statuses = controls["terminal_statuses"]
    runner_backed = controls["runner_backed_providers"]
    now_dt = datetime.now(timezone.utc)
    now_text = now_iso()
    changed = False

    cycles = state.setdefault("cycles", {})
    for cycle_id, cycle in cycles.items():
        status = cycle.get("status")
        if status in terminal_statuses:
            continue
        if active_statuses and status not in active_statuses:
            continue

        updated_at = parse_iso(cycle.get("updated_at") or state.get("updated_at"))
        if not updated_at:
            continue
        age_minutes = (now_dt - updated_at).total_seconds() / 60.0
        if age_minutes <= max_age_minutes:
            continue

        previous_status = status
        current_role = cycle.get("current_role")
        provider = cycle.get("current_provider") or (select_provider(current_role) if current_role else None)
        is_runner_timeout = previous_status == "role_dispatched" and provider in runner_backed
        cycle["previous_status"] = previous_status
        cycle["updated_at"] = now_text

        if is_runner_timeout:
            failure_type = "runner_unavailable"
            reason = (
                f"Role dispatch exceeded max_cycle_age_minutes={max_age_minutes}; "
                f"provider={provider} requires a self-hosted runner and did not return a result."
            )
            cycle["status"] = "blocked"
            cycle["blocked_at"] = now_text
            cycle["blocker"] = {
                "role": current_role,
                "provider": provider,
                "failure_type": failure_type,
                "reason": reason,
                "age_minutes": round(age_minutes, 2)
            }
            update_provider_status(provider, "error", failure_type=failure_type, reason=reason, role=current_role, cycle_id=cycle_id, trace_id=cycle.get("trace_id"))
            append_event({
                "event": "ROLE_PROVIDER_RUNNER_UNAVAILABLE",
                "cycle_id": cycle_id,
                "trace_id": cycle.get("trace_id"),
                "role": current_role,
                "provider": provider,
                "previous_status": previous_status,
                "max_cycle_age_minutes": max_age_minutes,
                "age_minutes": round(age_minutes, 2)
            })
            if post_reports:
                post_blocker_report(cycle_id, cycle, current_role, provider, reason, failure_type)
        else:
            cycle["status"] = "stale_timeout"
            cycle["stale_at"] = now_text
            cycle["stale_reason"] = f"Active cycle exceeded max_cycle_age_minutes={max_age_minutes}"
            append_event({
                "event": "ROLE_CYCLE_STALE_TIMEOUT",
                "cycle_id": cycle_id,
                "trace_id": cycle.get("trace_id"),
                "previous_status": previous_status,
                "max_cycle_age_minutes": max_age_minutes,
                "age_minutes": round(age_minutes, 2)
            })
        changed = True

    if changed:
        state["updated_at"] = now_text
        last_cycle_id = state.get("last_cycle_id")
        if last_cycle_id:
            last_status = cycles.get(last_cycle_id, {}).get("status")
            if last_status in {"stale_timeout", "blocked", "step_limit_exceeded"}:
                state["status"] = last_status
        write_json(STATE_PATH, state)
    return state


def adapter_for_provider(provider, role):
    policy = load_provider_adapters()
    adapter = policy.get("adapters", {}).get(provider)
    if not adapter:
        return None, "adapter_missing"
    if not adapter.get("enabled", False):
        return adapter, "adapter_disabled"
    supports = adapter.get("supports_roles", [])
    if supports and role not in supports:
        return adapter, "adapter_does_not_support_role"
    if adapter.get("mode") != "workflow_dispatch":
        return adapter, "adapter_not_workflow_dispatch"
    return adapter, None


def role_reserve_provider(role):
    routing = load_json(ROUTING_PATH, {})
    policy = load_provider_adapters()
    role_cfg = routing.get("roles", {}).get(role, {})
    return role_cfg.get("reserve") or policy.get("default_provider", "gpt")


def provider_is_unhealthy(provider, provider_status):
    item = provider_status.get("providers", {}).get(provider, {})
    status = item.get("status")
    failure_type = item.get("last_failure_type")
    return status in ("limited", "error") and (failure_type in UNHEALTHY_FAILURE_TYPES or status == "limited")


def select_provider(role):
    routing = load_json(ROUTING_PATH, {})
    provider_status = load_json(PROVIDER_STATUS_PATH, {"providers": {}})
    adapters_policy = load_provider_adapters()
    default_provider = adapters_policy.get("default_provider", "gpt")
    role_cfg = routing.get("roles", {}).get(role, {})
    candidates = []

    def add(candidate):
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    add(provider_failover_candidate(role))
    add(role_cfg.get("active") or role_cfg.get("primary") or default_provider)
    add(role_cfg.get("primary"))
    add(role_cfg.get("reserve"))
    for item in role_cfg.get("fallback_chain") or []:
        add(item)
    add(default_provider)
    add("gpt")

    for candidate in list(candidates):
        adapter, adapter_reason = adapter_for_provider(candidate, role)
        if adapter_reason:
            append_provider_adapter_event({"event": "PROVIDER_SKIPPED", "role": role, "provider": candidate, "reason": adapter_reason})
            continue
        if provider_is_unhealthy(candidate, provider_status):
            item = provider_status.get("providers", {}).get(candidate, {})
            append_provider_adapter_event({
                "event": "PROVIDER_SKIPPED",
                "role": role,
                "provider": candidate,
                "reason": "provider_unhealthy",
                "status": item.get("status"),
                "failure_type": item.get("last_failure_type")
            })
            continue
        return candidate

    append_provider_adapter_event({"event": "PROVIDER_SELECTION_DEGRADED", "role": role, "candidates": candidates, "reason": "no_healthy_candidate; falling back to first candidate"})
    return candidates[0] if candidates else default_provider


def resolve_provider_and_adapter(role):
    provider = select_provider(role)
    adapter, reason = adapter_for_provider(provider, role)
    if reason:
        original_provider = provider
        provider = role_reserve_provider(role)
        adapter, second_reason = adapter_for_provider(provider, role)
        append_provider_adapter_event({"event": "PROVIDER_ADAPTER_FALLBACK", "role": role, "from_provider": original_provider, "to_provider": provider, "reason": reason, "second_reason": second_reason})
        if second_reason:
            raise RuntimeError(f"No usable provider adapter for role={role}; provider={provider}; reason={second_reason}")
    append_provider_adapter_event({"event": "PROVIDER_ADAPTER_SELECTED", "role": role, "provider": provider, "workflow": adapter.get("workflow"), "mode": adapter.get("mode")})
    return provider, adapter


def github_api(method, url, payload=None):
    token = os.environ.get("AI_SYSTEM_GITHUB_PAT") or os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GitHub token environment variable is missing")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "ai-devops-role-orchestrator"
    })
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw else {"status": resp.status}


def post_issue_comment(body):
    repo = os.environ.get("GITHUB_REPOSITORY", "bereznyi-aleksandr/ai-devops-system")
    issue = os.environ.get("MAIN_ISSUE", MAIN_ISSUE)
    return github_api("POST", f"https://api.github.com/repos/{repo}/issues/{issue}/comments", {"body": body})


def dispatch_workflow(workflow_file, inputs):
    repo = os.environ.get("GITHUB_REPOSITORY", "bereznyi-aleksandr/ai-devops-system")
    return github_api("POST", f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_file}/dispatches", {"ref": os.environ.get("GITHUB_REF_NAME", "main"), "inputs": inputs})


def next_role_for_cycle(sequence, current_index):
    next_index = current_index + 1
    if next_index >= len(sequence):
        return None, next_index
    return sequence[next_index], next_index


def dispatch_role(cycle_id, trace_id, task_type, role, provider, task, adapter=None):
    adapter = adapter or adapter_for_provider(provider, role)[0]
    workflow = adapter.get("workflow") if adapter else ROLE_WORKFLOW
    mode = adapter.get("mode") if adapter else "workflow_dispatch"
    if mode != "workflow_dispatch":
        raise RuntimeError(f"Provider adapter for {provider} does not support workflow_dispatch")
    dispatch_workflow(workflow, {
        "role": role,
        "provider": provider,
        "trace_id": trace_id,
        "cycle_id": cycle_id,
        "task_type": task_type,
        "task": task[:4000]
    })


def start_cycle(task_type, task, trace_id=None, cycle_id=None):
    seq_policy = load_json(SEQUENCE_PATH, {})
    state = mark_stale_cycles(load_json(STATE_PATH, {"version": 1, "cycles": {}}), seq_policy)
    task_type = task_type or seq_policy.get("default_task_type", "default_development")
    sequence = seq_policy.get("task_types", {}).get(task_type)
    if not sequence:
        raise RuntimeError(f"Unknown task_type or empty sequence: {task_type}")
    cycle_id = cycle_id or ("cyc_" + uuid.uuid4().hex[:16])
    trace_id = trace_id or ("fsm_" + uuid.uuid4().hex[:16])
    role, index = next_role_for_cycle(sequence, -1)
    provider, adapter = resolve_provider_and_adapter(role)
    cycles = state.setdefault("cycles", {})
    cycles[cycle_id] = {
        "cycle_id": cycle_id,
        "trace_id": trace_id,
        "task_type": task_type,
        "sequence": sequence,
        "current_index": index,
        "current_role": role,
        "current_provider": provider,
        "status": "role_dispatched",
        "task": task,
        "step_count": 0,
        "step_history": [],
        "updated_at": now_iso()
    }
    cycle = cycles[cycle_id]
    if not register_role_step(state, cycle_id, cycle, "role_dispatch", role, provider, post_report=True):
        return cycle_id, trace_id, role, provider
    state["updated_at"] = now_iso()
    state["last_cycle_id"] = cycle_id
    state["last_trace_id"] = trace_id
    state["status"] = "cycle_started"
    write_json(STATE_PATH, state)
    dispatch_role(cycle_id, trace_id, task_type, role, provider, task, adapter)
    append_event({"event": "ROLE_CYCLE_STARTED", "cycle_id": cycle_id, "trace_id": trace_id, "task_type": task_type, "role": role, "provider": provider})
    return cycle_id, trace_id, role, provider


def finish_cycle_with_terminal_report(state, cycle, cycle_id, next_index, terminal_role):
    cycle["current_index"] = next_index
    cycle["current_role"] = terminal_role
    cycle["current_provider"] = None
    cycle["status"] = "completed"
    cycle["updated_at"] = now_iso()
    state["updated_at"] = now_iso()
    state["status"] = "cycle_completed"
    write_json(STATE_PATH, state)
    append_event({"event": "ROLE_CYCLE_TERMINAL_REPORT", "cycle_id": cycle_id, "trace_id": cycle.get("trace_id"), "role": terminal_role})
    post_issue_comment("BEM-ROLE-ORCHESTRATOR | CURATOR SUMMARY\n\n" + f"Cycle: {cycle_id}\nTrace: {cycle.get('trace_id')}\nTask type: {cycle.get('task_type')}\nStatus: completed\n" + "Summary: role FSM completed analyst -> auditor -> executor -> auditor.")
    append_event({"event": "ROLE_CYCLE_COMPLETED", "cycle_id": cycle_id, "trace_id": cycle.get("trace_id")})
    return None, None


def advance_cycle(cycle_id, role, status, note=""):
    seq_policy = load_json(SEQUENCE_PATH, {})
    state = mark_stale_cycles(load_json(STATE_PATH, {"version": 1, "cycles": {}}), seq_policy)
    cycles = state.setdefault("cycles", {})
    cycle = cycles.get(cycle_id)
    if not cycle:
        raise RuntimeError(f"Unknown cycle_id: {cycle_id}")
    if cycle.get("status") in {"stale_timeout", "blocked", "step_limit_exceeded"}:
        raise RuntimeError(f"Cycle is terminal and cannot advance: {cycle_id} status={cycle.get('status')}")

    if not register_role_step(state, cycle_id, cycle, "role_result", role, cycle.get("current_provider"), post_report=True):
        return None, None

    append_event({"event": "ROLE_RESULT_RECEIVED", "cycle_id": cycle_id, "trace_id": cycle.get("trace_id"), "role": role, "status": status, "note": note[:1000]})

    if status not in ("ROLE_DONE", "APPROVED"):
        cycle["status"] = "blocked"
        cycle["blocker"] = {"role": role, "status": status, "note": note}
        cycle["updated_at"] = now_iso()
        write_json(STATE_PATH, state)
        post_issue_comment("BEM-ROLE-ORCHESTRATOR | BLOCKED\n\n" + f"Cycle: {cycle_id}\nTrace: {cycle.get('trace_id')}\nRole: {role}\nStatus: {status}\nNote: {note[:1500]}")
        return None, None

    sequence = cycle.get("sequence", [])
    next_role, next_index = next_role_for_cycle(sequence, int(cycle.get("current_index", -1)))
    if not next_role:
        cycle["status"] = "completed"
        cycle["current_index"] = next_index
        cycle["current_role"] = None
        cycle["current_provider"] = None
        cycle["updated_at"] = now_iso()
        state["updated_at"] = now_iso()
        state["status"] = "cycle_completed"
        write_json(STATE_PATH, state)
        append_event({"event": "ROLE_CYCLE_COMPLETED", "cycle_id": cycle_id, "trace_id": cycle.get("trace_id")})
        post_issue_comment("BEM-ROLE-ORCHESTRATOR | CYCLE COMPLETED\n\n" + f"Cycle: {cycle_id}\nTrace: {cycle.get('trace_id')}\nTask type: {cycle.get('task_type')}\nStatus: completed")
        return None, None

    if next_role in TERMINAL_REPORT_ROLES:
        return finish_cycle_with_terminal_report(state, cycle, cycle_id, next_index, next_role)

    provider, adapter = resolve_provider_and_adapter(next_role)
    cycle["current_index"] = next_index
    cycle["current_role"] = next_role
    cycle["current_provider"] = provider
    cycle["status"] = "role_dispatched"
    cycle["updated_at"] = now_iso()
    if not register_role_step(state, cycle_id, cycle, "role_dispatch", next_role, provider, post_report=True):
        return None, None
    state["updated_at"] = now_iso()
    write_json(STATE_PATH, state)
    dispatch_role(cycle_id, cycle.get("trace_id"), cycle.get("task_type"), next_role, provider, cycle.get("task", ""), adapter)
    append_event({"event": "ROLE_DISPATCHED", "cycle_id": cycle_id, "trace_id": cycle.get("trace_id"), "role": next_role, "provider": provider})
    return next_role, provider


def watchdog_cycles():
    seq_policy = load_json(SEQUENCE_PATH, {})
    state = load_json(STATE_PATH, {"version": 1, "cycles": {}})
    before = json.dumps(state, sort_keys=True, ensure_ascii=False)
    state = mark_stale_cycles(state, seq_policy, post_reports=True)
    after = json.dumps(state, sort_keys=True, ensure_ascii=False)
    changed = before != after
    append_event({"event": "ROLE_WATCHDOG_COMPLETED", "changed": changed, "last_cycle_id": state.get("last_cycle_id"), "status": state.get("status")})
    return changed, state.get("last_cycle_id"), state.get("status")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["start", "advance", "watchdog"], required=True)
    parser.add_argument("--task-type", default="default_development")
    parser.add_argument("--task", default="")
    parser.add_argument("--trace-id", default="")
    parser.add_argument("--cycle-id", default="")
    parser.add_argument("--role", default="")
    parser.add_argument("--status", default="ROLE_DONE")
    parser.add_argument("--note", default="")
    args = parser.parse_args()
    append_event({"event": "ROLE_ORCHESTRATOR_START", "mode": args.mode})
    if emergency_stop_blocked(args.mode, args.trace_id, args.cycle_id):
        return 42
    if args.mode == "start":
        cycle_id, trace_id, role, provider = start_cycle(args.task_type, args.task, args.trace_id or None, args.cycle_id or None)
        print("BEM-ROLE-ORCHESTRATOR | STARTED")
        print("CYCLE_ID=" + cycle_id)
        print("TRACE_ID=" + trace_id)
        print("ROLE=" + str(role))
        print("PROVIDER=" + str(provider))
        return 0
    if args.mode == "watchdog":
        changed, cycle_id, status = watchdog_cycles()
        print("BEM-ROLE-ORCHESTRATOR | WATCHDOG")
        print("CHANGED=" + str(changed).lower())
        print("LAST_CYCLE_ID=" + str(cycle_id or "none"))
        print("STATUS=" + str(status or "unknown"))
        return 0
    next_role, provider = advance_cycle(args.cycle_id, args.role, args.status, args.note)
    print("BEM-ROLE-ORCHESTRATOR | ADVANCED")
    print("NEXT_ROLE=" + str(next_role or "none"))
    print("PROVIDER=" + str(provider or "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
