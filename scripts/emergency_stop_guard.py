#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
STATE = ROOT / "governance/state/emergency_stop.json"
EVENTS = ROOT / "governance/events/emergency_stop.jsonl"

def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def load_state():
    if not STATE.exists():
        return {
            "version": 1,
            "enabled": False,
            "updated_at": None,
            "updated_by": None,
            "reason": None,
            "trace_id": None
        }
    return json.loads(STATE.read_text(encoding="utf-8"))

def write_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def append_event(event):
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    event.setdefault("timestamp", now())
    with EVENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["enable", "disable", "check"], required=True)
    ap.add_argument("--trace-id", default="")
    ap.add_argument("--reason", default="")
    ap.add_argument("--scope", default="role_orchestrator")
    ap.add_argument("--actor", default="system")
    args = ap.parse_args()

    state = load_state()

    if args.mode == "enable":
        state.update({
            "enabled": True,
            "updated_at": now(),
            "updated_by": args.actor,
            "reason": args.reason or "manual emergency stop",
            "trace_id": args.trace_id
        })
        write_state(state)
        append_event({
            "event": "EMERGENCY_STOP_ENABLED",
            "trace_id": args.trace_id,
            "actor": args.actor,
            "reason": state["reason"],
            "scope": args.scope
        })
        print("BEM-EMERGENCY-STOP | ENABLED")
        return 0

    if args.mode == "disable":
        previous_reason = state.get("reason")
        state.update({
            "enabled": False,
            "updated_at": now(),
            "updated_by": args.actor,
            "reason": args.reason or "manual emergency stop disabled",
            "trace_id": args.trace_id
        })
        write_state(state)
        append_event({
            "event": "EMERGENCY_STOP_DISABLED",
            "trace_id": args.trace_id,
            "actor": args.actor,
            "reason": state["reason"],
            "previous_reason": previous_reason,
            "scope": args.scope
        })
        print("BEM-EMERGENCY-STOP | DISABLED")
        return 0

    if state.get("enabled"):
        append_event({
            "event": "EMERGENCY_STOP_BLOCKED",
            "trace_id": args.trace_id or state.get("trace_id"),
            "actor": args.actor,
            "reason": state.get("reason"),
            "scope": args.scope
        })
        print("BEM-EMERGENCY-STOP | BLOCKED")
        print("Reason: " + str(state.get("reason")))
        return 42

    print("BEM-EMERGENCY-STOP | CLEAR")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
