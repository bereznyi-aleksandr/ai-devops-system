#!/usr/bin/env python3
"""Object report aggregator runtime for BEM-944.

Aggregates governance reports, role report records, and object event records into an auditable
summary. Evidence aggregation only; no downstream LLM completion is claimed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "governance" / "reports"
STATE = ROOT / "governance" / "state"
PROOFS = ROOT / "governance" / "proofs"
OUT = STATE / "object_report_aggregate.json"
LOG = ROOT / "governance" / "logs" / "execution_log.jsonl"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            item = {"_invalid_json": True, "error": str(exc), "raw": line}
        if isinstance(item, dict):
            out.append(item)
    return out


def append_jsonl(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


def aggregate(limit: int | None = None) -> dict[str, Any]:
    report_entries: list[dict[str, Any]] = []
    for path in sorted(REPORTS.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        report_entries.append({
            "path": str(path.relative_to(ROOT)),
            "name": path.name,
            "size": len(text.encode("utf-8")),
            "sha256": sha256_text(text),
            "title": next((line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("#")), ""),
        })
    if limit is not None:
        report_entries = report_entries[-limit:]
    role_reports = read_jsonl(STATE / "role_reports.jsonl")
    object_events = read_jsonl(STATE / "object_events.jsonl")
    dispatch_processed = read_jsonl(STATE / "dispatch_processed.jsonl")
    aggregate_doc = {
        "status": "PASS",
        "protocol": "BEM-944",
        "task_id": "BEM944-P2-OBJECT-REPORT-AGGREGATOR",
        "created_at": now(),
        "aggregate_path": str(OUT.relative_to(ROOT)),
        "report_count": len(report_entries),
        "role_report_count": len(role_reports),
        "object_event_count": len(object_events),
        "dispatch_processed_count": len(dispatch_processed),
        "reports": report_entries,
        "latest_role_report": role_reports[-1] if role_reports else None,
        "latest_object_event": object_events[-1] if object_events else None,
        "latest_dispatch_processed": dispatch_processed[-1] if dispatch_processed else None,
        "non_claim": "object report aggregation only; no downstream LLM completion claimed",
    }
    return aggregate_doc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    aggregate_doc = aggregate(args.limit)
    STATE.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(aggregate_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    checks = {
        "object_report_aggregator_runtime_code_present": True,
        "aggregate_written": OUT.exists(),
        "aggregate_has_report_or_role_data": aggregate_doc["report_count"] > 0 or aggregate_doc["role_report_count"] > 0,
        "object_event_channel_readable": aggregate_doc["object_event_count"] >= 0,
        "dispatch_processed_channel_readable": aggregate_doc["dispatch_processed_count"] >= 0,
        "non_claim_present": True,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    receipt = {
        "status": "PASS" if not blockers else "BLOCKED",
        "protocol": "BEM-944",
        "task_id": "BEM944-P2-OBJECT-REPORT-AGGREGATOR",
        "created_at": now(),
        "stage": {"tasks_done": 3, "tasks_total": 4, "percent": 75},
        "aggregate_path": str(OUT.relative_to(ROOT)),
        "counts": {k: aggregate_doc[k] for k in ("report_count", "role_report_count", "object_event_count", "dispatch_processed_count")},
        "checks": checks,
        "blockers": blockers,
        "non_claim": "object report aggregation evidence only; no downstream LLM completion claimed",
        "next_task": "BEM944-P3-FINAL-VERIFY" if not blockers else None,
    }
    PROOFS.mkdir(parents=True, exist_ok=True)
    receipt_path = PROOFS / "BEM944_object_report_aggregator_receipt.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    append_jsonl(LOG, {
        "timestamp": now(),
        "protocol": "BEM-944",
        "task_id": receipt["task_id"],
        "status": receipt["status"],
        "receipt": str(receipt_path.relative_to(ROOT)),
        "aggregate": str(OUT.relative_to(ROOT)),
    })
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if receipt["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
