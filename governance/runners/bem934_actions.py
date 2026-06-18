#!/usr/bin/env python3
"""Repair BEM-934 provider-router embedded expectations and fallback notice."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REQUEST = ROOT / "governance/runtime/bem934_state_request.json"
WORKFLOW = ROOT / ".github/workflows/provider-router.yml"
RECEIPT = ROOT / "governance/proofs/BEM934_provider_router_test_alignment_receipt.json"

REPLACEMENTS = {
    'out["provider_selected"] == "gpt_codex" and out["fallback_reason"] is None and out["stale_ignored"] is True':
        'out["provider_selected"] == "claude_code" and out["fallback_reason"] is None and out["stale_ignored"] is True',
    'out["provider_selected"] == "claude_code" and out["fallback_reason"] == "fallback_quota" and out["decision_source"] == "same_trace_result"':
        'out["provider_selected"] == "gpt_codex_cloud" and out["fallback_reason"] == "fallback_quota" and out["decision_source"] == "same_trace_result"',
    'out["provider_selected"] == "gpt_codex" and out["fallback_reason"] is None and out["decision_source"] == "default"':
        'out["provider_selected"] == "claude_code" and out["fallback_reason"] is None and out["decision_source"] == "default"',
    '"text":"GPT quota exceeded -> fallback Claude запущен"':
        '"text":"Claude primary unavailable -> gpt_codex_cloud fallback запущен"',
}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)


def write(payload: dict[str, Any]) -> None:
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    request = json.loads(REQUEST.read_text(encoding="utf-8"))
    action = str(request.get("action") or "").strip()
    receipt: dict[str, Any] = {
        "status": "BLOCKED",
        "protocol": "BEM-934",
        "task_id": "BEM934-LIVE-TEST-PREP",
        "created_at": now(),
        "action": action,
        "checks": {},
        "missing": [],
    }
    if action != "repair_provider_router_tests":
        receipt["blocker"] = "unsupported_action"
        write(receipt)
        return 0

    pull = run(["git", "pull", "--rebase", "--autostash", "origin", "main"])
    if pull.returncode:
        receipt["blocker"] = "git_pull_failed"
        receipt["stderr"] = pull.stderr[-2000:]
        write(receipt)
        return 0

    source = WORKFLOW.read_text(encoding="utf-8")
    counts: dict[str, int] = {}
    for old, new in REPLACEMENTS.items():
        count = source.count(old)
        counts[old[:80]] = count
        if count:
            source = source.replace(old, new)
    WORKFLOW.write_text(source, encoding="utf-8")

    updated = WORKFLOW.read_text(encoding="utf-8")
    checks = {
        "healthy_primary_expectation_is_claude_code": updated.count(
            'out["provider_selected"] == "claude_code" and out["fallback_reason"] is None'
        ) >= 2,
        "quota_fallback_expectation_is_gpt_codex_cloud": (
            'out["provider_selected"] == "gpt_codex_cloud" and out["fallback_reason"] == "fallback_quota"'
            in updated
        ),
        "legacy_gpt_codex_assertions_absent": (
            'out["provider_selected"] == "gpt_codex"' not in updated
        ),
        "fallback_notice_names_current_providers": (
            "Claude primary unavailable -> gpt_codex_cloud fallback" in updated
        ),
        "router_compiles": run(["python3", "-m", "py_compile", "scripts/provider_router.py"]).returncode == 0,
    }
    receipt["checks"] = checks
    receipt["replacement_counts"] = counts
    receipt["missing"] = [key for key, value in checks.items() if not value]
    if receipt["missing"]:
        receipt["blocker"] = "provider_router_alignment_validation_failed"
        write(receipt)
        return 0

    run(["git", "config", "user.email", "bem934-router@ai-devops-system"])
    run(["git", "config", "user.name", "BEM-934 Router"])
    run(["git", "add", ".github/workflows/provider-router.yml"])
    diff = run(["git", "diff", "--cached", "--quiet"])
    commit_sha = None
    if diff.returncode != 0:
        commit = run(["git", "commit", "-m", "Align BEM-934 provider-router tests with current providers"])
        if commit.returncode:
            receipt["blocker"] = "git_commit_failed"
            receipt["stderr"] = commit.stderr[-2000:]
            write(receipt)
            return 0
        push = run(["git", "push"])
        if push.returncode:
            pull2 = run(["git", "pull", "--rebase", "origin", "main"])
            push2 = run(["git", "push"]) if pull2.returncode == 0 else pull2
            if pull2.returncode or push2.returncode:
                receipt["blocker"] = "git_push_failed"
                receipt["stderr"] = (pull2.stderr + "\n" + push2.stderr)[-3000:]
                write(receipt)
                return 0
    head = run(["git", "rev-parse", "HEAD"])
    if head.returncode == 0:
        commit_sha = head.stdout.strip()

    receipt.update({
        "status": "PASS",
        "source_commit_sha": commit_sha,
        "workflow_path": ".github/workflows/provider-router.yml",
        "next_verification": "dispatch provider-router.yml selftest",
    })
    receipt.pop("blocker", None)
    write(receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
