#!/usr/bin/env python3
"""BEM-932 provider router.

Selects the provider for a role/task without scanning stale result directories.
The public contract is a strict JSON/dict with exactly these keys:
provider_selected, fallback_reason, decision_source, trace_id, ttl_seconds, stale_ignored.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "governance" / "config" / "provider_config.json"


CONTRACT_KEYS = (
    "provider_selected",
    "fallback_reason",
    "decision_source",
    "trace_id",
    "ttl_seconds",
    "stale_ignored",
)


def _utc_now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


def _parse_ts(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


def _load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _is_fresh(record: Dict[str, Any], ttl_seconds: int, now_ts: Optional[float] = None) -> bool:
    now = _utc_now_ts() if now_ts is None else now_ts
    ts = (
        _parse_ts(record.get("created_at"))
        or _parse_ts(record.get("updated_at"))
        or _parse_ts(record.get("recorded_at"))
        or _parse_ts(record.get("timestamp"))
    )
    if ts is None:
        return False
    return now - ts <= ttl_seconds


def _normalize_reason(reason: Any) -> Optional[str]:
    if reason is None:
        return None
    text = str(reason).strip()
    if not text:
        return None
    lowered = text.lower()
    if "quota" in lowered:
        return "quota_exceeded"
    if "rate" in lowered and "limit" in lowered:
        return "rate_limit"
    if "unavailable" in lowered or "timeout" in lowered:
        return "provider_unavailable"
    return text


def _extract_error_reason(record: Any) -> Optional[str]:
    if not isinstance(record, dict):
        return None
    for key in ("error", "error_code", "status", "reason", "fallback_reason"):
        reason = _normalize_reason(record.get(key))
        if reason:
            return reason
    nested = record.get("result")
    if isinstance(nested, dict):
        return _extract_error_reason(nested)
    return None


def _same_trace_result_reason(config: Dict[str, Any], trace_id: str) -> tuple[Optional[str], bool]:
    """Check only governance/codex/results/{trace_id}.json, never the whole directory."""
    results_dir = ROOT / config.get("status_sources", {}).get("codex_results_dir", "governance/codex/results")
    path = results_dir / f"{trace_id}.json"
    record = _load_json(path, {})
    if not record:
        return None, False
    record_trace = str(record.get("trace_id") or trace_id)
    if record_trace != trace_id:
        return None, True
    return _extract_error_reason(record), False


def _provider_status_reason(config: Dict[str, Any], trace_id: str, ttl_seconds: int) -> tuple[Optional[str], bool]:
    status_path = ROOT / config.get("status_sources", {}).get("provider_status", "governance/state/provider_status.json")
    status = _load_json(status_path, {})
    if not isinstance(status, dict) or not status:
        return None, False

    candidates = []
    stale_ignored = False

    if isinstance(status.get(trace_id), dict):
        candidates.append(status[trace_id])

    records = status.get("records")
    if isinstance(records, list):
        for record in records:
            if not isinstance(record, dict):
                continue
            record_trace = str(record.get("trace_id", ""))
            # Other trace ids must never cause fallback. If their error is stale,
            # expose stale_ignored=True for audit/test visibility.
            if record_trace != trace_id:
                if _extract_error_reason(record) and not _is_fresh(record, ttl_seconds):
                    stale_ignored = True
                continue
            candidates.append(record)

    if str(status.get("trace_id", "")) == trace_id:
        candidates.append(status)
    elif _extract_error_reason(status) and not _is_fresh(status, ttl_seconds):
        stale_ignored = True

    for record in candidates:
        if not _is_fresh(record, ttl_seconds):
            stale_ignored = True
            continue
        reason = _extract_error_reason(record)
        if reason:
            return reason, stale_ignored
    return None, stale_ignored


def main(role: str, task_input: Any = None, trace_id: Optional[str] = None) -> Dict[str, Any]:
    config = _load_json(CONFIG_PATH, {})
    ttl_seconds = int(config.get("ttl_seconds", 1800))
    trace = str(trace_id or (task_input.get("trace_id") if isinstance(task_input, dict) else "") or "")
    if not trace:
        trace = f"trace_{int(time.time())}"

    roles = config.get("roles", {})
    role_config = roles.get(role, {})
    primary = role_config.get("primary", "gpt_codex")
    fallback = role_config.get("fallback", "claude_code")
    fallback_on = set(config.get("fallback_on", ["quota_exceeded", "rate_limit", "provider_unavailable"]))

    stale_ignored = False
    reason, stale = _same_trace_result_reason(config, trace)
    stale_ignored = stale_ignored or stale
    decision_source = "same_trace_result"

    if reason is None:
        reason, stale = _provider_status_reason(config, trace, ttl_seconds)
        stale_ignored = stale_ignored or stale
        decision_source = "provider_status" if reason else config.get("default_decision_source", "default")

    normalized = _normalize_reason(reason)
    if normalized in fallback_on:
        provider = fallback
        fallback_reason = "fallback_quota" if normalized == "quota_exceeded" else f"fallback_{normalized}"
    else:
        provider = primary
        fallback_reason = None

    result = {
        "provider_selected": provider,
        "fallback_reason": fallback_reason,
        "decision_source": decision_source,
        "trace_id": trace,
        "ttl_seconds": ttl_seconds,
        "stale_ignored": bool(stale_ignored),
    }
    return {key: result[key] for key in CONTRACT_KEYS}


def _cli() -> None:
    parser = argparse.ArgumentParser(description="BEM-932 provider router")
    parser.add_argument("--role", required=True, choices=["curator", "analyst", "auditor", "executor"])
    parser.add_argument("--task", default="")
    parser.add_argument("--trace-id", default="")
    args = parser.parse_args()
    task_input = {"task": args.task, "trace_id": args.trace_id}
    print(json.dumps(main(args.role, task_input, args.trace_id), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    _cli()
