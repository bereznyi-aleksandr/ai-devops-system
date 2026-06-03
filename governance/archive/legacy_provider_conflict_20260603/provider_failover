#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
POLICY = ROOT / "governance/policies/provider_failover_policy.json"
STATUS = ROOT / "governance/state/provider_status.json"
ROUTING = ROOT / "governance/state/routing.json"
EVENTS = ROOT / "governance/events/provider_failover.jsonl"


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path, default):
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_event(event):
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    event.setdefault("timestamp", now())
    with EVENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def normalize_status(raw):
    if isinstance(raw, dict):
        return raw.get("status") or raw.get("state") or "ok"
    if isinstance(raw, str):
        return raw
    return "ok"


def provider_statuses():
    state = load_json(STATUS, {})
    if "providers" in state and isinstance(state["providers"], dict):
        return state["providers"]
    return state if isinstance(state, dict) else {}


def select_provider(role, trace_id="", task_type=""):
    policy = load_json(POLICY, {"roles": {}})
    statuses = provider_statuses()
    role_policy = policy.get("roles", {}).get(role)
    if not role_policy:
        role_policy = {"primary": "gpt", "fallback_chain": ["gpt", "claude"]}

    unhealthy = set(policy.get("unhealthy_statuses", []))
    default_status = policy.get("default_provider_status", "ok")
    chain = role_policy.get("fallback_chain") or [role_policy.get("primary", "gpt")]

    inspected = []
    for provider in chain:
        item = statuses.get(provider, {})
        status = normalize_status(item) or default_status
        inspected.append({"provider": provider, "status": status})
        if status not in unhealthy:
            event = {
                "event": "PROVIDER_FAILOVER_SELECTED",
                "trace_id": trace_id,
                "task_type": task_type,
                "role": role,
                "provider": provider,
                "provider_status": status,
                "fallback_used": provider != role_policy.get("primary"),
                "inspected": inspected
            }
            append_event(event)
            return {"status": "ok", **event}

    event = {
        "event": "PROVIDER_FAILOVER_BLOCKED",
        "trace_id": trace_id,
        "task_type": task_type,
        "role": role,
        "reason": "no_healthy_provider",
        "inspected": inspected
    }
    append_event(event)
    return {"status": "blocked", **event}


def mark_provider(provider, status, reason="", trace_id=""):
    state = load_json(STATUS, {"providers": {}})
    if "providers" not in state or not isinstance(state["providers"], dict):
        state = {"providers": state if isinstance(state, dict) else {}}
    current = state["providers"].get(provider, {})
    if not isinstance(current, dict):
        current = {"status": str(current)}
    current.update({
        "status": status,
        "reason": reason,
        "updated_at": now(),
        "trace_id": trace_id
    })
    state["providers"][provider] = current
    write_json(STATUS, state)
    append_event({
        "event": "PROVIDER_STATUS_MARKED",
        "trace_id": trace_id,
        "provider": provider,
        "status": status,
        "reason": reason
    })


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("select")
    s.add_argument("--role", required=True)
    s.add_argument("--trace-id", default="")
    s.add_argument("--task-type", default="")

    m = sub.add_parser("mark")
    m.add_argument("--provider", required=True)
    m.add_argument("--status", required=True)
    m.add_argument("--reason", default="")
    m.add_argument("--trace-id", default="")

    args = ap.parse_args()
    if args.cmd == "select":
        result = select_provider(args.role, args.trace_id, args.task_type)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if result.get("status") == "blocked":
            return 42
        print("BEM-PROVIDER-FAILOVER | SELECTED | " + result.get("provider", "unknown"))
        return 0
    if args.cmd == "mark":
        mark_provider(args.provider, args.status, args.reason, args.trace_id)
        print("BEM-PROVIDER-FAILOVER | MARKED | " + args.provider + " | " + args.status)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
