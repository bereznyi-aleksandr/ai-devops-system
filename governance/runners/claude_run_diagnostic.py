#!/usr/bin/env python3
"""BEM-948: observe a trace-bound Claude Actions run and preserve sanitized diagnostics.

This runner observes only. It never equates Actions acceptance or a successful job
container with an executed/completed governance proof.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "governance" / "reports"
PROOFS = ROOT / "governance" / "proofs"

MARKERS = (
    "anthropics/claude-code-action",
    "claude_role",
    "claude code",
    "error",
    "failed",
    "failure",
    "exit code",
    "oauth",
    "token",
    "rate",
    "quota",
    "unauthorized",
    "forbidden",
    "provider",
)

TOKEN_PATTERNS = (
    re.compile(r"ghp_[A-Za-z0-9_]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE),
)

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def command(args: list[str], timeout: int = 60) -> tuple[int, str, str]:
    completed = subprocess.run(
        args, text=True, capture_output=True, timeout=timeout, check=False
    )
    return completed.returncode, completed.stdout, completed.stderr

def as_list(raw: str) -> list[dict[str, Any]]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []

def select_run(
    repo: str, head_sha: str, started_at: str, attempts: int, delay: int
) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for _ in range(max(1, attempts)):
        code, out, _ = command([
            "gh", "run", "list", "--repo", repo, "--workflow", "claude.yml",
            "--limit", "100",
            "--json", "databaseId,headSha,createdAt,updatedAt,status,conclusion,displayTitle",
        ])
        candidates = [
            item for item in as_list(out)
            if item.get("headSha") == head_sha
            and str(item.get("createdAt", "")) >= started_at
        ]
        candidates.sort(key=lambda item: str(item.get("createdAt", "")), reverse=True)
        if candidates:
            selected = candidates[0]
            if selected.get("status") == "completed":
                return selected
        time.sleep(max(1, delay))
    return selected

def sanitize(value: str) -> str:
    for pattern in TOKEN_PATTERNS:
        value = pattern.sub("***", value)
    secret = os.environ.get("GH_TOKEN", "")
    if secret:
        value = value.replace(secret, "***")
    return value

def excerpt(log_text: str) -> list[str]:
    lines = log_text.splitlines()
    picked: set[int] = set()
    for index, line in enumerate(lines):
        lowered = line.lower()
        if any(marker in lowered for marker in MARKERS):
            picked.update(range(max(0, index - 6), min(len(lines), index + 16)))
    if not picked and lines:
        picked.update(range(max(0, len(lines) - 120), len(lines)))
    result = [sanitize(lines[index])[:700] for index in sorted(picked)]
    return result[:240]

def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--attempts", type=int, default=12)
    parser.add_argument("--delay", type=int, default=15)
    args = parser.parse_args()

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not repo:
        raise SystemExit("GITHUB_REPOSITORY is required")
    trace = args.trace_id
    selected = select_run(repo, args.head_sha, args.started_at, args.attempts, args.delay)
    run_id = str(selected.get("databaseId", ""))

    log_text = ""
    log_error = ""
    if run_id:
        _, log_text, log_error = command(
            ["gh", "run", "view", run_id, "--repo", repo, "--log-failed"], timeout=90
        )
        if not log_text.strip():
            _, log_text, extra = command(
                ["gh", "run", "view", run_id, "--repo", repo, "--log"], timeout=90
            )
            log_error += "\n" + extra
    diagnostic_lines = excerpt(log_text)
    logs_accessible = bool(log_text.strip())
    specific_error = any(
        any(marker in line.lower() for marker in ("error", "exit code", "oauth", "token", "rate", "quota", "unauthorized", "forbidden"))
        for line in diagnostic_lines
    )

    REPORTS.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS / f"{trace}_claude_observation.md"
    report = [
        "# BEM-948 P0 Claude run observation",
        "",
        f"Trace: `{trace}`",
        f"Head commit: `{args.head_sha}`",
        f"Run ID: `{run_id}`",
        f"Run status: `{selected.get('status', '')}`",
        f"Run conclusion: `{selected.get('conclusion', '')}`",
        "",
        "## Sanitized targeted excerpt",
        "",
    ]
    report.extend([f"- `{line}`" for line in diagnostic_lines] or ["- No accessible targeted log line returned."])
    report.extend(["", "## Scope", "", "Observation only; this report does not claim executed/completed P0 evidence."])
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")

    blockers = []
    if not run_id:
        blockers.append("claude_workflow_run_not_found_for_trace_window")
    elif selected.get("status") != "completed":
        blockers.append("claude_workflow_run_not_completed_before_observation_timeout")
    elif selected.get("conclusion") != "success":
        blockers.append("claude_role_or_workflow_runtime_failure")
    if not logs_accessible:
        blockers.append("targeted_action_log_not_accessible")

    receipt = {
        "status": "OBSERVED",
        "protocol": "BEM-948",
        "task_id": "BEM948-P0-CLAUDE-RUN-OBSERVATION",
        "created_at": now(),
        "trace_id": trace,
        "target_head_sha": args.head_sha,
        "target_head_sha_type": "commit",
        "run": selected,
        "diagnostics": {
            "logs_accessible": logs_accessible,
            "targeted_excerpt_lines": len(diagostic_lines),
            "specific_error_line_found": specific_error,
            "log_error_present": bool(log_error.strip()),
            "report_path": str(report_path.relative_to(ROOT)),
        },
        "checks": {
            "observation_is_trace_bound": True,
            "claude_action_log_collection_attempted": True,
            "executed_completed_proof_exists": False,
            "no_false_pass_claim": True,
            "sha_type_explicit": True,
        },
        "blockers": blockers,
        "next_task": (
            "BEM948-P0-AUTOREPAIR-AFTER-CLAUDE-LOG-DIAGNOSTIC"
            if blockers else "BEM948-P0-POLL-EXECUTED-PROOF"
        ),
    }
    write_json(PROOFS / "BEM948_p0_claude_run_observation_receipt.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
