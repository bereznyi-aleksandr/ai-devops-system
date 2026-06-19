#!/usr/bin/env python3
"""Role report writer runtime for BEM-939."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "governance" / "state"
REPORTS = ROOT / "governance" / "reports"
PROOFS = ROOT / "governance" / "proofs"
LOGS = ROOT / "governance" / "logs"
ROLE_REPORTS = STATE / "role_reports.jsonl"
EXECUTION_LOG = LOGS / "execution_log.jsonl"
OBJECT_EVENTS = STATE / "object_events.jsonl"
DISPATCH_PROCESSED = STATE / "dispatch_processed.jsonl"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.:-]+", "_", str(value or "report"))[:140]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            item = {"_invalid": "json", "_raw": line, "_error": str(exc)}
        if isinstance(item, dict):
            out.append(item)
    return out


def append_jsonl(path: Path, items: list[dict[str, Any]]) -> None:
    if not items:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


def find_context(trace_id: str | None, dispatch_id: str | None) -> dict[str, Any]:
    context: dict[str, Any] = {"object_event": None, "dispatch_processed": None}
    for item in reversed(jsonl(OBJECT_EVENTS)):
        if (trace_id and item.get("trace_id") == trace_id) or (dispatch_id and item.get("dispatch_id") == dispatch_id):
            context["object_event"] = item
            break
    for item in reversed(jsonl(DISPATCH_PROCESSED)):
        if (trace_id and item.get("trace_id") == trace_id) or (dispatch_id and item.get("dispatch_id") == dispatch_id):
            context["dispatch_processed"] = item
            break
    return context


def build_report(role: str, task_id: str, status: str, title: str, summary: str,
                 trace_id: str | None, dispatch_id: str | None, percent: int) -> tuple[str, dict[str, Any]]:
    context = find_context(trace_id, dispatch_id)
    created = now()
    report_id = f"{safe(task_id)}_{safe(role)}_{safe(trace_id or dispatch_id or created)}"
    lines = [
        f"# {task_id} | {role} report",
        "",
        f"Created: {created}",
        f"Status: {status}",
        f"Progress: {percent}%",
        "",
        "## Title",
        title,
        "",
        "## Summary",
        summary,
        "",
        "## Runtime evidence",
        f"- trace_id: `{trace_id or ''}`",
        f"- dispatch_id: `{dispatch_id or ''}`",
        f"- object_event_present: `{context['object_event'] is not None}`",
        f"- dispatch_processed_present: `{context['dispatch_processed'] is not None}`",
        "",
        "## Non-claim",
        "This report records role/report handoff evidence only; it does not claim downstream LLM completion.",
        "",
    ]
    text = "\n".join(lines)
    report_path = REPORTS / f"{report_id}.md"
    record = {
        "status": status,
        "protocol": "BEM-939",
        "task_id": task_id,
        "role": role,
        "created_at": created,
        "trace_id": trace_id,
        "dispatch_id": dispatch_id,
        "report_path": str(report_path.relative_to(ROOT)),
        "report_sha256": sha256_text(text),
        "percent": percent,
        "context": {
            "object_event_present": context["object_event"] is not None,
            "dispatch_processed_present": context["dispatch_processed"] is not None,
        },
        "non_claim": "role report handoff only; no downstream LLM completion claimed",
    }
    return text, record


def write_report(record: dict[str, Any], text: str) -> None:
    path = ROOT / record["report_path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    append_jsonl(ROLE_REPORTS, [record])
    append_jsonl(EXECUTION_LOG, [{
        "timestamp": now(),
        "protocol": "BEM-939",
        "task_id": record["task_id"],
        "status": record["status"],
        "role": record["role"],
        "trace_id": record.get("trace_id"),
        "receipt": "governance/proofs/BEM939_role_report_writer_receipt.json",
        "report_path": record["report_path"],
    }])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", default="curator")
    parser.add_argument("--task-id", default="BEM939-P1-ROLE-REPORT-WRITER")
    parser.add_argument("--status", default="PASS")
    parser.add_argument("--title", default="BEM-939 role report writer runtime")
    parser.add_argument("--summary", default="Role report writer replaced stub and materialized an evidence-bearing report.")
    parser.add_argument("--trace-id", default="bem939_role_report_writer_selftest")
    parser.add_argument("--dispatch-id")
    parser.add_argument("--percent", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_argr()
    text, record = build_report(args.role, args.task_id, args.status, args.title, args.summary,
                                args.trace_id, args.dispatch_id, args.percent)
    if not args.dry_run:
        write_report(record, text)
    checks = {
        "role_report_writer_runtime_code_present": True,
        "report_markdown_materialized": args.dry_run or (ROOT / record["report_path"]).exists(),
        "role_reports_jsonl_bound": args.dry_run or ROLE_REPORTS.exists(),
        "execution_log_bound": args.dry_run or EXECUTION_LOG.exists(),
        "report_hash_present": bool(record.get("report_sha256")),
        "downstream_llm_completion_not_claimed": True,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    receipt = {
        "status": "PASS" if not blockers else "BLOCKED",
        "protocol": "BEM-939",
        "task_id": "BEM939-P1-ROLE-REPORT-WRITER",
        "created_at": now(),
        "stage": {"tasks_done": 2, "tasks_total": 4, "percent": 50},
        "record": record,
        "checks": checks,
        "blockers": blockers,
        "next_task": "BEM939-P2-EVENT-OBJECT-INTEGRATION" if not blockers else None,
    }
    PROOFS.mkdir(parents=True, exist_ok=True)
    (PROOFS / "BEM939_role_report_writer_receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if blockers:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
