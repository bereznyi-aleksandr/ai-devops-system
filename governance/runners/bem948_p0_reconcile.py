#!/usr/bin/env python3
"""BEM-948 P0 evidence reconciler.

Reads repository-local evidence only. It does not change status to PASS and
does not manufacture an executed/completed proof.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROOFS = ROOT / "governance" / "proofs"
REPORTS = ROOT / "governance" / "reports"
OUTPUT = PROOFS / "BEM948_p0_reconciliation_receipt.json"
REPORT = REPORTS / "bem948_p0_reconciliation.md"
ALLOWED_SHA_TYPES = {"git_blob", "commit", "sha256_content"}

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)
    return (value, None) if isinstance(value, dict) else (None, "json_root_not_object")

def blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    return hashlib.sha1(f"blob {len(payload)}\0".encode("utf-8") + payload).hexdigest()

def has_conflict_marker(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return any(marker in text for marker in ("<<<<<<<", "=======", ">>>>>>>"))

def explicit_sha_type_violations(value: Any, location: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key.endswith("_sha") and child:
                type_key = f"{key}_type"
                if value.get(type_key) not in ALLOWED_SHA_TYPES:
                    violations.append(f"{location}.{key}")
            violations.extend(explicit_sha_type_violations(child, f"{location}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(explicit_sha_type_violations(child, f"{location}[{index}]"))
    return violations

def main() -> int:
    proof_rows: list[dict[str, Any]] = []
    report_rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    completed_traces: set[str] = set()
    failed_traces: set[str] = set()
    sha_type_violations: list[str] = []
    conflict_files: list[str] = []

    for path in sorted(PROOFS.glob("BEM948*.json")):
        payload, error = load_json(path)
        relative = str(path.relative_to(ROOT))
        row: dict[str, Any] = {
            "path": relative,
            "blob_sha": blob_sha(path),
            "blob_sha_type": "git_blob",
            "parse_error": error,
        }
        if payload:
            row["status"] = payload.get("status")
            row["task_id"] = payload.get("task_id")
            row["trace_id"] = payload.get("trace_id")
            row["dispatch_result"] = payload.get("dispatch_result")
            row["blocker"] = payload.get("blocker")
            violations = explicit_sha_type_violations(payload)
            if violations:
                sha_type_violations.extend(f"{relative}:{item}" for item in violations)
            if payload.get("status") == "completed" and payload.get("trace_id"):
                completed_traces.add(str(payload["trace_id"]))
        proof_rows.append(row)
        if has_conflict_marker(path):
            conflict_files.append(relative)

    for path in sorted(REPORTS.glob("bem948*.md")):
        relative = str(path.relative_to(ROOT))
        text = path.read_text(encoding="utf-8", errors="replace")
        trace = ""
        for line in text.splitlines():
            if "Trace" in line and "`" in line:
                trace = line.split("`", 2)[1]
                break
        lowered = text.lower()
        outcome = "failure" if "outcome: `failure`" in lowered or "outcome | failure" in lowered else ""
        if outcome == "failure" and trace:
            failed_traces.add(trace)
        report_rows.append({
            "path": relative,
            "blob_sha": blob_sha(path),
            "blob_sha_type": "git_blob",
            "trace_id": trace or None,
            "outcome": outcome or None,
            "has_conflict_marker": has_conflict_marker(path),
        })
        if has_conflict_marker(path):
            conflict_files.append(relative)

    contradictory_traces = sorted(completed_traces.intersection(failed_traces))
    if contradictory_traces:
        blockers.append("proof_report_outcome_conflict")
    if sha_type_violations:
        blockers.append("executed_proof_sha_policy_invalid")
    if conflict_files:
        blockers.append("report_merge_conflict_markers")
    if not completed_traces:
        blockers.append("executed_completed_proof_absent")

    receipt = {
        "status": "BLOCKED_REPAIRING" if blockers else "RECONCILED",
        "protocol": "BEM-948",
        "task_id": "BEM948-P0-RECONCILE-PROOF-REPORT-AND-REPAIR-CLAUDE-TRANSPORT",
        "created_at": now(),
        "proofs": proof_rows,
        "reports": report_rows,
        "completed_traces": sorted(completed_traces),
        "failed_traces": sorted(failed_traces),
        "contradictory_traces": contradictory_traces,
        "sha_type_violations": sha_type_violations,
        "conflict_marker_files": sorted(set(conflict_files)),
        "checks": {
            "repository_evidence_scanned": True,
            "sha_type_policy_checked": True,
            "proof_report_correlation_checked": True,
            "no_false_p0_pass_claim": True,
        },
        "blockers": blockers,
        "next_task": (
            "BEM948-P0-REPAIR-CLAUDE-TRANSPORT"
            if blockers else "BEM948-P0-LIVE-OBJECT-E2E"
        ),
    }
    OUTPUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_lines = [
        "# BEM-948 P0 reconciliation",
        "",
        f"Completed proof traces: `{', '.join(sorted(completed_traces)) or 'none'}`",
        f"Failure report traces: `{', '.join(sorted(failed_traces)) or 'none'}`",
        f"Contradictory traces: `{', '.join(contradictory_traces) or 'none'}`",
        f"SHA-type violations: `{len(sha_type_violations)}`",
        f"Conflict-marker files: `{', '.join(sorted(set(conflict_files))) or 'none'}`",
        "",
        f"Result: `{receipt['status']}`. No P0 PASS is claimed.",
    ]
    REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
