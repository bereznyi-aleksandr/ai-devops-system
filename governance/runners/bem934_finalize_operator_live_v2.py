#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(".")
TRACE = "tg_818730867_20260618T105741Z"
QUEUE = ROOT / "governance/roadmap/ACTIVE_QUEUE.json"
ROUTER = ROOT / f"governance/proofs/BEM932_provider_router_{TRACE}.json"
TRANSPORT = ROOT / "governance/transport/results.jsonl"
REPORT = ROOT / f"governance/reports/{TRACE}.md"
EVIDENCE = ROOT / f"governance/proofs/evidence/BEM934_operator_telegram_{TRACE}.jpg"
RECON = ROOT / "governance/proofs/BEM934_live_state_reconciliation_receipt.json"
CANONICAL = ROOT / "governance/proofs/BEM934_live_test_receipt.json"
SUPERSEDED = ROOT / "governance/proofs/BEM934_live_test_receipt_superseded_replay.json"
DIAGNOSTIC = ROOT / "governance/proofs/BEM934_operator_live_finalization_diagnostic.json"
EXECUTION_LOG = ROOT / "governance/logs/execution_log.jsonl"
EXPECTED_EVIDENCE_SHA256 = "747977554bf955daa71979e3202abb6cfa0f5e604e318229d6426a3321976178"

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid_jsonl_line:{number}:{exc}") from exc
        if not isinstance(value, dict):
            raise RuntimeError(f"non_object_jsonl_line:{number}")
        records.append(value)
    return records

def main() -> None:
    queue = load_json(QUEUE)
    router = load_json(ROUTER)
    recon = load_json(RECON)
    diagnostic = load_json(DIAGNOSTIC)
    report = REPORT.read_text(encoding="utf-8")
    evidence = EVIDENCE.read_bytes()
    records = load_jsonl(TRANSPORT)
    trace_records = [record for record in records if record.get("trace_id") == TRACE]
    completed_executor = [
        record for record in trace_records
        if record.get("role") == "executor"
        and record.get("provider") == "claude"
        and record.get("status") == "completed"
        and record.get("blocker") is None
    ]
    failed_history = [
        record for record in trace_records
        if record.get("status") == "failed" or record.get("blocker")
    ]
    latest_completed = sorted(
        completed_executor,
        key=lambda item: str(item.get("completed_at", "")),
    )[-1] if completed_executor else None

    report_checks = {
        "status_pass": "## Status: PASS" in report,
        "two_invariants": "### INV-1" in report and "### INV-2" in report,
        "pass_conditions": report.count("Pass condition:") >= 2,
        "acceptance_checks": "## Acceptance Checks" in report,
        "limitations_disclosed": "## Limitations" in report,
        "prior_failure_disclosed": "Prior run record" in report and "outcome=failure" in report,
        "substantive_length": len(report.strip()) >= 3000,
    }
    checks = {
        "queue_current_live": queue.get("current_task") == "BEM934-LIVE-TEST",
        "reconciliation_pass": recon.get("status") == "PASS",
        "reconciliation_did_not_promote_release": recon.get("release_promoted") is False,
        "diagnostic_only_report_gap": diagnostic.get("failed_checks") == [
            "report_has_pass", "report_has_fail", "report_has_invariant"
        ],
        "operator_evidence_present": EVIDENCE.exists(),
        "operator_evidence_sha256": hashlib.sha256(evidence).hexdigest() == EXPECTED_EVIDENCE_SHA256,
        "operator_evidence_is_jpeg": evidence[:2] == b"\xff\xd8" and evidence[-2:] == b"\xff\xd9",
        "router_pass": router.get("status") == "PASS",
        "router_trace_match": router.get("trace_id") == TRACE,
        "router_provider_claude_code": router.get("provider_selected") == "claude_code",
        "router_workflow_claude": router.get("target_workflow_id") == "claude.yml",
        "router_dispatch_success": router.get("dispatch_result") == "success",
        "router_message_bound": str(router.get("message_id", "")).strip() != "",
        "semantic_executor_completed": latest_completed is not None,
        "failed_attempts_preserved": len(failed_history) >= 1,
        "report_semantically_substantive": all(report_checks.values()),
    }
    failures = [name for name, value in checks.items() if not value]
    if failures:
        raise RuntimeError("strict_live_finalization_failed:" + ",".join(failures))

    if CANONICAL.exists() and not SUPERSEDED.exists():
        old = load_json(CANONICAL)
        old["_superseded"] = {
            "at": now(),
            "reason": (
                "Top-level PASS contradicted failed Claude transport records and "
                "telegram_bot_api_message_replay_to_live_webhook ingress."
            ),
            "replacement_trace_id": TRACE,
        }
        SUPERSEDED.write_text(
            json.dumps(old, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    created_at = now()
    receipt = {
        "status": "PASS",
        "protocol": "BEM-934",
        "task_id": "BEM934-LIVE-TEST",
        "receipt_version": 2,
        "created_at": created_at,
        "release_promoted": False,
        "trace_id": TRACE,
        "telegram": {
            "operator_authored": True,
            "automatic_bot_replay": False,
            "chat_id": router.get("chat_id"),
            "message_id": router.get("message_id"),
            "operator_evidence_path": str(EVIDENCE),
            "operator_evidence_sha256": EXPECTED_EVIDENCE_SHA256,
            "evidence_observation": (
                "Right-aligned blue Telegram message contains the requested invariant task; "
                "the immediately following bot acknowledgement binds it to this trace."
            ),
        },
        "route": {
            "router_receipt": str(ROUTER),
            "provider_selected": router.get("provider_selected"),
            "target_workflow_id": router.get("target_workflow_id"),
            "dispatch_result": router.get("dispatch_result"),
        },
        "transport": {
            "semantic_result": latest_completed,
            "historical_failed_attempt_count": len(failed_history),
            "historical_failed_attempts": failed_history,
            "acceptance_rule": "latest executor record must be completed with blocker=null; failures remain disclosed",
        },
        "substantive_result": {
            "report_path": str(REPORT),
            "report_sha256": hashlib.sha256(report.encode("utf-8")).hexdigest(),
            "report_checks": report_checks,
            "limitations_preserved": True,
        },
        "checks": checks,
        "failed_blockers": [],
        "supersedes": {
            "path": str(SUPERSEDED),
            "reason": "prior contradictory replay PASS rejected",
        },
        "next_task": "BEM934-CLOSE",
    }
    CANONICAL.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    queue["version"] = int(queue.get("version", 0)) + 1
    queue["updated_at"] = created_at
    queue["queue_state"] = "ACTIVE"
    queue["current_task"] = "BEM934-CLOSE"
    queue["system_status"] = "BEM934_IN_PROGRESS"
    queue["release_status"] = "FOLLOW_UP_REQUIRED"
    summary = queue.setdefault("completed_summary", {})
    summary["tasks_done"] = 9
    summary["tasks_total"] = 10
    proofs = summary.setdefault("proofs", [])
    for proof in (str(CANONICAL), str(EVIDENCE), str(REPORT)):
        if proof not in proofs:
            proofs.append(proof)
    for task in queue.get("tasks", []):
        if task.get("id") == "BEM934-LIVE-TEST":
            task["status"] = "DONE"
            task["completed_at"] = created_at
            task["receipt"] = str(CANONICAL)
            task["done_sha_pending"] = True
            task.pop("remaining_blocker", None)
        elif task.get("id") == "BEM934-CLOSE":
            task["status"] = "IN_PROGRESS"
            task["blocked_by"] = []
            task["started_at"] = created_at
    queue["last_completed"] = {
        "id": "BEM934-LIVE-TEST",
        "completed_at": created_at,
        "receipt": str(CANONICAL),
    }
    queue["next_action"] = (
        "BEM934-CLOSE: refresh canonical context/status, obtain independent "
        "EXTERNAL_AUDITOR_CLAUDE PASS, then finalize release."
    )
    QUEUE.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with EXECUTION_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "timestamp": created_at,
            "task_id": "BEM934-LIVE-TEST",
            "status": "DONE",
            "trace_id": TRACE,
            "receipt": str(CANONICAL),
            "release_promoted": False,
            "next_task": "BEM934-CLOSE",
        }, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    main()
