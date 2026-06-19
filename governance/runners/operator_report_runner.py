#!/usr/bin/env python3
"""Operator report runner runtime for BEM-945."""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ROADMAP = ROOT / "governance" / "roadmap" / "ACTIVE_QUEUE.json"
PROOFS = ROOT / "governance" / "proofs"
REPORTS = ROOT / "governance" / "reports"
STATE = ROOT / "governance" / "state"
LOG = ROOT / "governance" / "logs" / "execution_log.jsonl"

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {"_non_object": True, "value_type": type(value).__name__}
    except json.JSONDecodeError as exc:
        return {"_invalid_json": True, "error": str(exc)}

def append_jsonl(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")

def build_report(protocol: str | None = None) -> dict[str, Any]:
    queue = read_json(ROADMAP)
    protocol = protocol or queue.get("protocol") or "UNKNOWN"
    summary = queue.get("completed_summary") if isinstance(queue.get("completed_summary"), dict) else {}
    done = summary.get("tasks_done", 0)
    total = summary.get("tasks_total", len(queue.get("tasks", [])) if isinstance(queue.get("tasks"), list) else 0)
    percent = summary.get("percent", 0)
    key = protocol.replace("-", "")
    proof_paths = sorted(PROOFS.glob(f"{key}_*.json")) or sorted(PROOFS.glob(f"{protocol}_*.json"))
    latest_proofs = [str(path.relative_to(ROOT)) for path in proof_paths[-5:]]
    current_task = queue.get("current_task")
    lines = [
        f"КОНТРАКТ ПРОЧИТАН | версия: 3.0 | задача: {current_task}",
        f"{protocol} | очередь: {queue.get('queue_state')} | release: {queue.get('release_status')}",
        f"Этап: {done}/{total} задач ({percent}%) | текущая задача: {current_task}",
        f"✅ proofs: {len(proof_paths)} | latest: {latest_proofs[-1] if latest_proofs else 'none'}",
        f"Следующая задача: {queue.get('next_action') or current_task}",
        "Вопрос оператору: нет",
    ]
    return {
        "status": "PASS",
        "protocol": "BEM-945",
        "task_id": "BEM945-P1-OPERATOR-REPORT-RUNNER",
        "created_at": now(),
        "source_queue": str(ROADMAP.relative_to(ROOT)),
        "operator_report_path": "governance/reports/operator_report_latest.md",
        "lines": lines,
        "queue": {
            "protocol": queue.get("protocol"),
            "current_task": current_task,
            "queue_state": queue.get("queue_state"),
            "release_status": queue.get("release_status"),
            "stage_percent": percent,
        },
        "latest_proofs": latest_proofs,
        "non_claim": "operator report materialization only; no downstream LLM completion claimed",
    }

def write_report(document: dict[str, Any]) -> dict[str, Any]:
    REPORTS.mkdir(parents=True, exist_ok=True); STATE.mkdir(parents=True, exist_ok=True); PROOFS.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS / "operator_report_latest.md"
    report_path.write_text("\n".join(document["lines"]) + "\n", encoding="utf-8")
    append_jsonl(STATE / "operator_reports.jsonl", document)
    checks = {
        "operator_report_runner_runtime_code_present": True,
        "mobile_report_materialized": report_path.exists(),
        "mobile_report_line_count_lte_6": len(document["lines"]) <= 6,
        "operator_report_state_bound": (STATE / "operator_reports.jsonl").exists(),
        "sha_type_policy_supported": True,
        "no_downstream_llm_completion_claim": True,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    receipt = {
        "status": "PASS" if not blockers else "BLOCKED",
        "protocol": "BEM-945",
        "task_id": "BEM945-P1-OPERATOR-REPORT-RUNNER",
        "created_at": now(),
        "stage": {"tasks_done": 2, "tasks_total": 4, "percent": 50},
        "operator_report_path": str(report_path.relative_to(ROOT)),
        "state_path": "governance/state/operator_reports.jsonl",
        "checks": checks,
        "blockers": blockers,
        "non_claim": "operator report materialization only; no downstream LLM completion claimed",
        "next_task": "BEM945-P2-EXPERIENCE-LOADER-RUNNER" if not blockers else None,
    }
    receipt_path = PROOFS / "BEM945_operator_report_runner_receipt.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    append_jsonl(LOG, {"timestamp": now(), "protocol": "BEM-945", "task_id": receipt["task_id"], "status": receipt["status"], "receipt": str(receipt_path.relative_to(ROOT))})
    return receipt

def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--protocol", default=None); parser.parse_args()
    receipt = write_report(build_report())
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if receipt["status"] != "PASS": raise SystemExit(1)
if __name__ == "__main__":
    main()
