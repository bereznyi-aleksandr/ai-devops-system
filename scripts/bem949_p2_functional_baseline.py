#!/usr/bin/env python3
"""Create a traceable BEM-949 P2 before/after functional baseline from Git history."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "governanc" / "proofs" / "BEM949_p2_functional_baseline.json"
REPORT = ROOT / "governance" / "reports" / "BEM949_p2_functional_before_after.md"

TARGETS = (
    ".github/workflows/bem934-binding-failure-log-inspector.yml",
    ".github/workflows/bem931-v36-release-repair-gate.yml",
    ".github/workflows/bem947-live-object-dispatch-retry.yml",
    ".github/workflows/bem948-live-object-e2e.yml",
    ".github/workflows/bem948-p0-claude-diagnostic-retry.yml",
)

VALIDATOR_MARKERS = (
    "Validate archived",
    "Validate retired",
    "syntax-safe",
    "Confirm workflow source is available",
)

FUNCTION_MARKERS = (
    "gh workflow run",
    "governance/proofs",
    "dispatch",
    "provider",
    "trace",
    "receipt",
    "repair-gate",
    "retry",
)


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def behavior(text: str) -> str:
    lower = text.lower()
    if any(marker.lower() in lower for marker in VALIDATOR_MARKERS):
        return "syntax_validator_only"
    if "gh workflow run" in lower or "dispatch" in lower:
        return "dispatch_or_retry_orchestration"
    if "governance/proofs" in lower or "receipt" in lower:
        return "receipt_or_proof_materialization"
    return "unclassified"


def historical_candidate(path: str) -> dict:
    commits = git("log", "--all", "--format=%H", "--", path).splitlines()
    for commit in commits[1:]:
        try:
            text = git("show", f"{commit}:{path}")
        except subprocess.CalledProcessError:
            continue
        kind = behavior(text)
        if kind != "syntax_validator_only":
            return {
                "commit_sha": commit,
                "commit_sha_type": "commit",
                "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "content_sha256_type": "sha256_content",
                "behavior": kind,
                "name_line": first_line(text),
                "function_markers": [marker for marker in FUNCTION_MARKERS if marker in text.lower()],
            }
    return {
        "commit_sha": None,
        "commit_sha_type": None,
        "content_sha256": None,
        "content_sha256_type": None,
        "behavior": "not_found_in_reachable_history",
        "name_line": None,
        "function_markers": [],
    }


def main() -> int:
    rows = []
    for path in TARGETS:
        current = (ROOT / path).read_text(encoding="utf-8")
        current_sha = git("hash-object", path)
        rows.append(
            {
                "path": path,
                "current_blob_sha": current_sha,
                "current_blob_sha_type": "git_blob",
                "current_behavior": behavior(current),
                "current_name_line": first_line(current),
                "historical_candidate": historical_candidate(path),
                "restoration_requirement": "P2 must restore a safe-gated functional scenario; do not relabel a syntax validator as functional restoration.",
            }
        )

    payload = {
        "schema_version": 1,
        "protocol": "BEM-949",
        "task_id": "BEM949-P2-FUNCTIONAL-RESTORE",
        "receipt_id": "BEM949_p2_functional_baseline",
        "created_at": now(),
        "status": "OBSERVED",
        "scope": "Before/after baseline only; no workflow functionality is restored by this artifact.",
        "workflow_count": len(rows),
        "workflows": rows,
        "checks": {
            "all_five_audited_workflows_enumerated": len(rows) == 5,
            "current_blob_sha_types_explicit": True,
            "historical_candidates_searched_in_reachable_git_history": True,
            "functional_restore_claimed": False,
        },
        "next_task": "BEM949-P2-FUNCTIONAL-RESTORE",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# BEM-949 P2 — Functional before/after baseline",
        "",
        "| Workflow | Current behavior | Historical candidate | Candidate behavior |",
        "|---|---|---:|---:|",
    ]
    for row in rows:
        candidate = row["historical_candidate"]
        sha = candidate["commit_sha"] or "not found"
        lines.append(
            f"| `{row['path']}` | {row['current_behavior']} | `{sha}` | {candidate['behavior']} |"
        )
    lines.extend([
        "",
        "This is an observed baseline. Restoring a safe-gated live path remains a separate P2 procedure.",
    ])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
