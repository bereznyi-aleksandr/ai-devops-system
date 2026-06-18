#!/usr/bin/env python3
"""Reconcile BEM-934 LIVE evidence without promoting a false release PASS."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(".")
QUEUE_PATH = ROOT / "governance/roadmap/ACTIVE_QUEUE.json"
TRANSPORT_PATH = ROOT / "governance/transport/results.jsonl"
RECEIPT_PATH = ROOT / "governance/proofs/BEM934_live_state_reconciliation_receipt.json"
EXECUTION_LOG_PATH = ROOT / "governance/logs/execution_log.jsonl"

REPLAY_TRACE = "tg_934432449_20260618T102008Z"
REAL_TRACE = "tg_818730867_20260618T105741Z"
REAL_ROUTER_PATH = ROOT / f"governance/proofs/BEM932_provider_router_{REAL_TRACE}.json"
OLD_LIVE_RECEIPT_PATH = ROOT / "governance/proofs/BEM934_live_test_receipt.json"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def clean_transport_jsonl(path: Path) -> tuple[list[dict[str, Any]], bool]:
    original = path.read_text(encoding="utf-8")
    cleaned_lines: list[str] = []
    invalid: list[str] = []
    changed = False
    for raw in original.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith(("<<<<<<<", "=======", ">>>>>>>")):
            changed = True
            continue
        try:
            json.loads(stripped)
        except json.JSONDecodeError:
            invalid.append(stripped[:240])
            continue
        cleaned_lines.append(stripped)
    if invalid:
        raise RuntimeError(f"transport_jsonl_has_unparseable_lines={len(invalid)}")
    cleaned_text = "\n".join(cleaned_lines) + "\n"
    if cleaned_text != original:
        path.write_text(cleaned_text, encoding="utf-8")
        changed = True
    return [json.loads(line) for line in cleaned_lines], changed


def latest_completed(records: list[dict[str, Any]], trace_id: str) -> dict[str, Any] | None:
    matches = [
        record
        for record in records
        if record.get("trace_id") == trace_id
        and record.get("provider") == "claude"
        and record.get("status") == "completed"
        and record.get("blocker") is None
    ]
    return sorted(matches, key=lambda item: str(item.get("completed_at", "")))[-1] if matches else None


def old_receipt_is_contradictory(path: Path) -> tuple[bool, dict[str, Any]]:
    if not path.exists():
        return False, {"exists": False}
    data = load_json(path)
    transport = data.get("transport_results")
    failed = [
        item
        for item in transport or []
        if isinstance(item, dict)
        and (item.get("status") == "failed" or item.get("blocker"))
    ]
    telegram = data.get("telegram") if isinstance(data.get("telegram"), dict) else {}
    replay = telegram.get("ingress_mode") == "telegram_bot_api_message_replay_to_live_webhook"
    contradictory = data.get("status") == "PASS" and (bool(failed) or replay)
    return contradictory, {
        "exists": True,
        "top_level_status": data.get("status"),
        "failed_transport_count": len(failed),
        "replay_ingress_disclosed": replay,
    }


def main() -> None:
    queue = load_json(QUEUE_PATH)
    records, transport_cleaned = clean_transport_jsonl(TRANSPORT_PATH)
    replay_completed = latest_completed(records, REPLAY_TRACE)
    real_completed = latest_completed(records, REAL_TRACE)
    router = load_json(REAL_ROUTER_PATH)

    router_checks = {
        "status_pass": router.get("status") == "PASS",
        "provider_selected_claude_code": router.get("provider_selected") == "claude_code",
        "target_workflow_claude_yml": router.get("target_workflow_id") == "claude.yml",
        "trace_matches": router.get("trace_id") == REAL_TRACE,
        "message_id_present": str(router.get("message_id", "")).strip() != "",
        "dispatch_success": router.get("dispatch_result") == "success",
    }
    old_contradictory, old_summary = old_receipt_is_contradictory(OLD_LIVE_RECEIPT_PATH)
    checks = {
        "transport_jsonl_parseable": True,
        "replay_trace_semantic_transport_completed": replay_completed is not None,
        "real_operator_candidate_router_receipt_valid": all(router_checks.values()),
        "real_operator_candidate_transport_completed": real_completed is not None,
        "old_live_receipt_rejected_as_contradictory": old_contradictory,
        "close_not_promoted": queue.get("current_task") == "BEM934-LIVE-TEST",
    }
    hard_failures = [
        key for key in (
            "transport_jsonl_parseable",
            "replay_trace_semantic_transport_completed",
            "real_operator_candidate_router_receipt_valid",
            "real_operator_candidate_transport_completed",
            "old_live_receipt_rejected_as_contradictory",
        ) if not checks[key]
    ]
    if hard_failures:
        raise RuntimeError("reconciliation_failed:" + ",".join(hard_failures))

    explicit_operator_ingress_bound = False
    receipt = {
        "status": "PASS",
        "protocol": "BEM-934",
        "task_id": "BEM934-LIVE-TEST-RECONCILIATION",
        "created_at": now(),
        "release_promoted": False,
        "live_task_closed": False,
        "checks": checks,
        "transport_jsonl_conflict_markers_removed": transport_cleaned,
        "replay_trace": {
            "trace_id": REPLAY_TRACE,
            "semantic_transport": replay_completed,
            "classification": "infrastructure_replay_only_not_operator_authored",
        },
        "real_operator_candidate": {
            "trace_id": REAL_TRACE,
            "router_receipt": str(REAL_ROUTER_PATH),
            "router_checks": router_checks,
            "semantic_transport": real_completed,
            "explicit_operator_authored_ingress_evidence_bound": explicit_operator_ingress_bound,
        },
        "superseded_live_receipt": {
            "path": str(OLD_LIVE_RECEIPT_PATH),
            "rejected": old_contradictory,
            "summary": old_summary,
        },
        "live_test_ready_for_strict_finalization": False,
        "blocker": "explicit_operator_authored_telegram_webhook_evidence_not_bound_to_final_receipt",
        "next_action": (
            "Bind an explicit operator-authored Telegram webhook/update artifact "
            f"to trace {REAL_TRACE}; then create a strict non-contradictory LIVE receipt."
        ),
    }
    RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT_PATH.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    queue["version"] = int(queue.get("version", 0)) + 1
    queue["updated_at"] = receipt["created_at"]
    queue["queue_state"] = "ACTIVE"
    queue["current_task"] = "BEM934-LIVE-TEST"
    queue["system_status"] = "BEM934_IN_PROGRESS"
    queue["release_status"] = "FOLLOW_UP_REQUIRED"
    summary = queue.setdefault("completed_summary", {})
    summary["tasks_done"] = 8
    summary["tasks_total"] = 10
    for task in queue.get("tasks", []):
        if task.get("id") == "BEM934-LIVE-TEST":
            task["status"] = "IN_PROGRESS"
            task["reconciliation_receipt"] = str(RECEIPT_PATH)
            task["transport_repair"] = {
                "replay_trace_completed": True,
                "real_operator_candidate_trace_completed": True,
            }
            task["remaining_blocker"] = receipt["blocker"]
        elif task.get("id") == "BEM934-CLOSE":
            task["status"] = "PENDING"
            task["blocked_by"] = ["BEM934-LIVE-TEST"]
    queue["next_action"] = receipt["next_action"]
    QUEUE_PATH.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    EXECUTION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_record = {
        "timestamp": receipt["created_at"],
        "task_id": "BEM934-LIVE-TEST-RECONCILIATION",
        "status": "DONE",
        "receipt": str(RECEIPT_PATH),
        "release_promoted": False,
        "next_task": "BEM934-LIVE-TEST",
    }
    with EXECUTION_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(log_record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
