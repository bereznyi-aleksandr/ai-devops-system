#!/usr/bin/env python3
"""Inspect trace-bound dispatch and execution logs without creating execution claims."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES = (
    "governance/state/dispatch_processed.jsonl",
    "governance/state/dispatch_executed.jsonl",
    "governance/logs/execution_log.jsonll",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    scanned = []
    matches = []
    for relative in DEFAULT_SOURCES:
        path = ROOT / relative
        item = {"path": relative, "exists": path.is_file(), "matching_lines": 0}
        if path.is_file():
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
            ):
                if args.trace_id in line:
                    item["matching_lines"] += 1
                    matches.append({"path": relative, "line": lineno, "raw": line[:500]})
        scanned.append(item)

    report_path = ROOT / "governance/reports" / f"{args.trace_id}_binding_inspection.md"
    terminal_report = ROOT / "governance/reports" / f"{args.trace_id}.md"
    terminal_exists = terminal_report.is_file()

    lines = [
        f"# Binding inspection — {args.trace_id}",
        "",
        f"Observed at: `{utc_now()}`",
        f"Terminal provider report present: `{str(terminal_exists).lower()}`",
        "",
        "## Sources",
        "",
        "| Source | Exists | Matching lines |",
        "|---|--:|---:|",
    ]
    for item in scanned:
        lines.append(
            f"| `{item['path']}` | {str(item['exists']).lower()} | {item['matching_lines']} |"
        )
    lines.extend(["", "## Trace matches", ""])
    if matches:
        for item in matches:
            lines.append(f"- `{item['path']}:{item['line'}`")
    else:
        lines.append("- No matching line was found in the configured sources.")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    receipt = {
        "schema_version": 1,
        "protocol": "BEM-949",
        "task_id": "BEM949-P2-FUNCTIONAL-RESTORE",
        "component": "bem934-binding-failure-log-inspector",
        "trace_id": args.trace_id,
        "created_at": utc_now(),
        "status": "OBSERVED" if matches or terminal_exists else "NOT_FOUND",
        "scope": "Trace-log inspection only; no provider execution or recovery claim.",
        "report_path": report_path.relative_to(ROOT).as_posix(),
        "terminal_provider_report_path": terminal_report.relative_to(ROOT).as_posix(),
        "terminal_provider_report_present": terminal_exists,
        "sources": scanned,
        "trace_matches": matches,
        "checks": {
            "configured_sources_scanned": True,
            "terminal_report_presence_checked": True,
            "no_execution_claim_from_log_inspection": True,
        },
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
