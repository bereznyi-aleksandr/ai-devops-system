#!/usr/bin/env python3
"""Provider-neutral, cost-policy-aware BEM-932 router."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "governance/config/provider_config.json"
STATE_PATH = ROOT / "governance/state/provider_status.json"
RESULTS_DIR = ROOT / "governance/codex/results"
CONTRACT_KEYS = (
    "provider_selected",
    "fallback_reason",
    "decision_source",
    "trace_id",
    "ttl_seconds",
    "stale_ignored",
)
FAILURE_MARKERS = ("quota", "rate limit", "unavailable", "timeout")


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default
    except Exception:
        return default


def parse_time(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    try:
        return float(value)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def fresh(record: dict[str, Any], ttl_seconds: int) -> bool:
    for key in ("created_at", "updated_at", "recorded_at", "timestamp", "last_failure_at"):
        timestamp = parse_time(record.get(key))
        if timestamp is not None:
            return time.time() - timestamp <= ttl_seconds
    return False


def failure_reason(record: Any) -> str | None:
    if not isinstance(record, dict):
        return None
    for key in ("error", "error_code", "reason", "status", "failure_type", "fallback_reason"):
        value = str(record.get(key, "")).lower()
        if any(marker in value for marker in FAILURE_MARKERS):
            return "quota_exceeded" if "quota" in value else "provider_unavailable"
    nested = record.get("result")
    return failure_reason(nested) if isinstance(nested, dict) else None


def provider_candidates(config: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    providers = config.get("providers", {})
    if not isinstance(providers, dict):
        return []
    candidates = [
        (provider_id, spec)
        for provider_id, spec in providers.items()
        if isinstance(provider_id, str)
        and isinstance(spec, dict)
        and spec.get("enabled") is True
    ]
    return sorted(candidates, key=lambda item: (int(item[1].get("priority", 999)), item[0]))


def has_cost_blocked_provider(config: dict[str, Any]) -> bool:
    providers = config.get("providers", {})
    return isinstance(providers, dict) and any(
        isinstance(spec, dict) and spec.get("status") == "DISABLED_BY_COST_POLICY"
        for spec in providers.values()
    )


def current_trace_reason(trace_id: str, ttl_seconds: int) -> tuple[str | None, bool]:
    stale_ignored = False
    sources = [RESULTS_DIR / f"{trace_id}.json", STATE_PATH]
    for source in sources:
        value = load_json(source, {})
        records: list[dict[str, Any]] = []
        if isinstance(value, dict):
            records.append(value)
            listed = value.get("records")
            if isinstance(listed, list):
                records.extend(item for item in listed if isinstance(item, dict))
        for record in records:
            record_trace = str(record.get("trace_id", ""))
            reason = failure_reason(record)
            if record_trace == trace_id and reason and fresh(record, ttl_seconds):
                return reason, stale_ignored
            if reason and record_trace != trace_id:
                stale_ignored = True
    return None, stale_ignored


def forced_reason(task: str) -> str | None:
    lowered = task.lower()
    return "quota_exceeded" if any(marker in lowered for marker in ("force-fallback", "force fallback", "quota-fallback", "quota fallback")) else None


def main(role: str, task: str, trace_id: str) -> dict[str, Any]:
    config = load_json(CONFIG_PATH, {})
    if not isinstance(config, dict):
        raise ValueError("provider_config.json must be a JSON object")
    candidates = provider_candidates(config)
    if not candidates:
        raise RuntimeError("no enabled provider is configured")

    ttl_seconds = int(config.get("ttl_seconds", 1800))
    selected = candidates[0][0]
    reason = forced_reason(task)
    source = "operator_forced_fallback" if reason else "same_trace_result"
    stale_ignored = False
    if reason is None:
        reason, stale_ignored = current_trace_reason(trace_id, ttl_seconds)
        source = "provider_status" if reason else "default"

    if reason:
        fallback_reason = "fallback_blocked_cost_policy" if has_cost_blocked_provider(config) else "fallback_unavailable"
        source = "cost_policy" if has_cost_blocked_provider(config) else source
    else:
        fallback_reason = Noe

    result = {
        "provider_selected": selected,
        "fallback_reason": fallback_reason,
        "decision_source": source,
        "trace_id": trace_id,
        "ttl_seconds": ttl_seconds,
        "stale_ignored": stale_ignored,
    }
    return {key: result[key] for key in CONTRACT_KEYS}


def cli() -> None:
    parser = argparse.ArgumentParser(description="BEM-932 provider router")
    parser.add_argument("--role", required=True, choices=("curator", "analyst", "auditor", "executor"))
    parser.add_argument("--task", default="")
    parser.add_argument("--trace-id", default="")
    args = parser.parse_args()
    trace_id = args.trace_id or f"trace_{int(time.time())}"
    print(json.dumps(main(args.role, args.task, trace_id), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    cli()
