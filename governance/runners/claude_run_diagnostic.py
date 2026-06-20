#!/usr/bin/env python3
"""Trace-bound, nondisclosing observer for a dispatched Claude Actions run."""
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
TOKEN_PATTERNS = (
    re.compile(r"ghp_[A-Za-z0-9_]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
)
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
)

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def call(args: list[str], timeout: int = 90) -> tuple[int, str, str]:
    completed = subprocess.run(
        ["gh", *args],
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    return completed.returncode, completed.stdout, completed.stderr

def list_runs(repo: str, head_sha: str) -> list[dict[str, Any]]:
    _, stdout, _ = call([
        "run", "list",
        "--repo", repo,
        "--workflow", "claude.yml",
        "--limit", "100",
        "--json", "databaseId,headSha,createdAt,updatedAt,status,conclusion,displayTitle",
    ])
    try:
        candidates = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    if not isinstance(candidates, list):
        return []
    return [
        item for item in candidates
        if isinstance(item, dict) and item.get("headSha") == head_sha
    ]

def select_run(
    repo: str,
    head_sha: str,
    started_at: str,
    attempts: int,
    delay: int,
) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for _ in range(max(1, attempts)):
        candidates = [
            item for item in list_runs(repo, head_sha)
            if str(item.get("createdAt", "")) >= started_at
        ]
        candidates.sort(key=lambda item: str(item.get("createdAt", "")), reverse=True)
        if candidates:
            selected = candidates[0]
            if selected.get("status") == "completed":
                break
        time.sleep(max(1, delay))
    return selected

def sanitize(value: str) -> str:
    token = os.environ.get("GH_TOKEN", "")
    if token:
        value = value.replace(token, "***")
    for pattern in TOKEN_PATTERNS:
        value = pattern.sub("***", value)
    return value

def targeted_excerpt(raw_log: str) -> list[str]:
    lines = raw_log.splitlines()
    selected: set[int] = set()
    for index, line in enumerate(lines):
        lowered = line.lower()
        if any(marker in lowered for marker in MARKERS):
            selected.update(range(max(0, index - 6), min(len(lines), index + 16)))
    if not selected and lines:
        selected.update(range(max(0, len(lines) - 120), len(lines)))
    return [sanitize(lines[index])[:700] for index in sorted(selected)][:240]

def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

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

    run = select_run(repo, args.head_sha, args.started_at, args.attempts, args.delay)
    run_id = str(run.get("databaseId", ""))
    raw_log = ""
    log_error = ""
    if run_id:
        _, raw_log, log_error = call(
            ["run", "view", run_id, "--repo", repo, "--log-failed"],
            timeout=120,
        )
        if not raw_log.strip():
            _, raw_log, fallback_error = call(
                ["run", "view", run_id, "--repo", repo, "--log"],
                timeout=120,
            )
            log_error = (log_error + "\n" + fallback_error).strip()
    excerpt = targeted_excerpt(raw_log)
    blockers: list[str] = []
    if not run_id:
        blockers.append("claude_workflow_run_not_found_for_trace_window")
    elif run.get("status") != "completed":
        blockers.append("claude_workflow_run_not_completed_before_observation_timeout")
    elif run.get("conclusion") != "success":
        blockers.append("claude_role_or_workflow_runtime_failure")
    if not raw_log.strip():
        blockers.append("targeted_action_log_not_accessible")

    REPORTS.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS / f"{args.trace_id}_claude_observation.md"
    report_lines = [
        "# BEM-948 P0 Claude run observation",
        "",
        f"Trace: `{args.trace_id}`",
        f"Target head commit: `{args.head_sha}`",
        f"Run ID: `{run_id}`",
        f"Run status: `{run.get('status', '')}`",
        f"Run conclusion: `{run.get('conclusion', '')}`",
        "",
        "## Sanitized targeted excerpt",
        "",
    ]
    report_lines.extend([f"- `{line}`" for line in excerpt] or ["- No accessible targeted log line returned."])
    report_lines.extend([
        "",
        "## Scope",
        "",
        "Observation only; no executed/completed P0 evidence is claimed by this observer.",
    ])
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    receipt = {
        "status": "OBSERVED",
        "protocol": "BEM-948",
        "task_id": "BEM948-P0-CLAUDE-RUN-OBSERVATION",
        "created_at": now(),
        "trace_id": args.trace_id,
        "target_head_sha": args.head_sha,
        "target_head_sha_type": "commit",
        "run": run,
        "diagnostic": {
            "logs_accessible": bool(raw_log.strip()),
            "targeted_excerpt_lines": len(excerpt),
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
            "BEM948-P0-REPAIR-CLAUDE-TRANSPORT"
            if blockers else "BEM948-P0-POLL-EXECUTED-PROOF"
        ),
    }
    write_json(PROOFS / "BEM948_p0_claude_run_observation_receipt.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
