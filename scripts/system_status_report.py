#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()

ROLE_STATE = ROOT / "governance/state/role_cycle_state.json"
PROVIDER_STATE = ROOT / "governance/state/provider_status.json"
EMERGENCY_STATE = ROOT / "governance/state/emergency_stop.json"
ROLE_EVENTS = ROOT / "governance/events/role_orchestrator.jsonl"
PROVIDER_EVENTS = ROOT / "governance/events/provider_adapter.jsonl"
RELAY_EVENTS = ROOT / "governance/events/gpt_autonomy_relay_events.jsonl"
SYSTEM_EVENTS = ROOT / "governance/events/system_status_reports.jsonl"
LATEST_REPORT = ROOT / "governance/reports/system_status_latest.md"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path, default):
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def tail_jsonl(path, limit=5):
    if not path.exists():
        return []
    lines = [x for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except Exception:
            out.append({"raw": line[:500]})
    return out


def append_event(event):
    SYSTEM_EVENTS.parent.mkdir(parents=True, exist_ok=True)
    with SYSTEM_EVENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def status_icon(value):
    if value in (False, "ok", "clear", "completed", "cycle_completed"):
        return "✅"
    if value in (True, "blocked", "error", "limited", "stale_timeout", "step_limit_exceeded"):
        return "❌"
    return "⚠️"


def build_report(mode, trace_id):
    ts = now_iso()
    role_state = load_json(ROLE_STATE, {"status": "unknown", "cycles": {}})
    provider_state = load_json(PROVIDER_STATE, {"providers": {}})
    emergency_state = load_json(EMERGENCY_STATE, {"enabled": False})

    last_cycle_id = role_state.get("last_cycle_id")
    cycles = role_state.get("cycles", {})
    last_cycle = cycles.get(last_cycle_id, {}) if last_cycle_id else {}

    emergency_enabled = bool(emergency_state.get("enabled"))
    providers = provider_state.get("providers", {})

    provider_lines = []
    if providers:
        for name, item in sorted(providers.items()):
            provider_lines.append(
                f"| {name} | {status_icon(item.get('status'))} {item.get('status', 'unknown')} | "
                f"{item.get('last_failure_type', '') or '-'} | {item.get('last_role', '') or '-'} |"
            )
    else:
        provider_lines.append("| none | ⚠️ unknown | - | - |")

    recent_role_events = tail_jsonl(ROLE_EVENTS, 5)
    recent_provider_events = tail_jsonl(PROVIDER_EVENTS, 5)
    recent_relay_events = tail_jsonl(RELAY_EVENTS, 5)

    checklist = [
        f"[{'❌' if emergency_enabled else '✅'}] emergency_stop.enabled = {str(emergency_enabled).lower()}",
        f"[✅] role_state.status = {role_state.get('status', 'unknown')}",
        f"[✅] last_cycle_id = {last_cycle_id or 'none'}",
        f"[✅] providers_checked = {len(providers)}",
        f"[✅] relay_events_seen = {len(recent_relay_events)}",
        f"[✅] report_generated_at = {ts}",
    ]

    report = "\n".join([
        "## BEM-SYSTEM-STATUS | RUN RESULT",
        "",
        "```text",
        f"Trace: {trace_id or 'system_status_report'}",
        f"Mode: {mode}",
        f"Time: {ts}",
        "",
        "ЧЕК-ЛИСТ:",
        *checklist,
        "```",
        "",
        "| Subsystem | Status | Detail |",
        "|---|---|---|",
        f"| Emergency stop | {status_icon(emergency_enabled)} {'enabled' if emergency_enabled else 'clear'} | {emergency_state.get('reason') or '-'} |",
        f"| Role FSM | {status_icon(role_state.get('status'))} {role_state.get('status', 'unknown')} | last_cycle={last_cycle_id or 'none'} |",
        f"| Last role | {status_icon(last_cycle.get('status'))} {last_cycle.get('status', 'unknown')} | role={last_cycle.get('current_role') or '-'} provider={last_cycle.get('current_provider') or '-'} |",
        f"| Relay | ✅ present | recent_events={len(recent_relay_events)} |",
        "",
        "### Providers",
        "",
        "| Provider | Status | Last failure | Last role |",
        "|---|---|---|---|",
        *provider_lines,
        "",
        "### Recent role events",
        "",
        "```json",
        json.dumps(recent_role_events, indent=2, ensure_ascii=False),
        "```",
        "",
        "### Recent provider events",
        "",
        "```json",
        json.dumps(recent_provider_events, indent=2, ensure_ascii=False),
        "```",
        "",
        "### Recent relay events",
        "",
        "```json",
        json.dumps(recent_relay_events, indent=2, ensure_ascii=False),
        "```",
    ])

    return report, {
        "event": "SYSTEM_STATUS_REPORT_GENERATED",
        "trace_id": trace_id,
        "mode": mode,
        "timestamp": ts,
        "emergency_stop_enabled": emergency_enabled,
        "role_state_status": role_state.get("status", "unknown"),
        "last_cycle_id": last_cycle_id,
        "providers_checked": len(providers)
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="manual")
    ap.add_argument("--trace-id", default="system_status_report")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    report, event = build_report(args.mode, args.trace_id)
    print(report)

    if args.write:
        LATEST_REPORT.parent.mkdir(parents=True, exist_ok=True)
        LATEST_REPORT.write_text(report + "\n", encoding="utf-8")
        append_event(event)
        print("BEM-SYSTEM-STATUS | WRITTEN")
    else:
        print("BEM-SYSTEM-STATUS | DRY_RUN")


if __name__ == "__main__":
    raise SystemExit(main())
