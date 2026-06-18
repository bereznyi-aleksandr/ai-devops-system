#!/usr/bin/env python3
"""Increase only the BEM-934 structured binding role turn budget."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REQUEST = ROOT / "governance/runtime/bem934_state_request.json"
WORKFLOW = ROOT / ".github/workflows/claude.yml"
RECEIPT = ROOT / "governance/proofs/BEM934_binding_max_turns_repair_receipt.json"


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
        "task_id": "BEM934-OBJECTS-BOUND",
        "created_at": now(),
        "action": action,
        "checks": {},
        "missing": [],
    }
    if action != "increase_binding_structured_output_turns":
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
    start = source.find("id: claude_binding_role")
    end = source.find("- name: Materialize BEM-934 binding plan", start)
    if start < 0 or end < 0:
        receipt["blocker"] = "binding_role_or_materializer_marker_missing"
        write(receipt)
        return 0

    block = source[start:end]
    old_count = block.count("--max-turns 10")
    if old_count:
        block = block.replace("--max-turns 10", "--max-turns 30", 1)
        source = source[:start] + block + source[end:]
        WORKFLOW.write_text(source, encoding="utf-8")

    updated = WORKFLOW.read_text(encoding="utf-8")
    start2 = updated.find("id: claue_binding_role")
    end2 = updated.find("- name: Materialize BEM-934 binding plan", start2)
    block2 = updated[start2:end2]
    checks = {
        "dedicated_binding_role_present": start2 >= 0,
        "binding_max_turns_is_30": "--max-turns 30" in block2,
        "binding_max_turns_10_absent": "--max-turns 10" not in block2,
        "json_schema_preserved": "--json-schema" in block2,
        "structured_output_materializer_preserved": (
            "outputs.structured_output" in updated[end2:]
        ),
        "normal_role_still_present": "id: claude_role" in updated,
    }
    receipt["checks"] = checks
    receipt["old_occurrences_repaired"] = old_count
    receipt["missing"] = [key for key, value in checks.items() if not value]
    if receipt["missing"]:
        receipt["blocker"] = "binding_turn_budget_validation_failed"
        write(receipt)
        return 0

    run(["git", "config", "user.email", "bem934-binding@ai-devops-system"])
    run(["git", "config", "user.name", "BEM-934 Binding"])
    run(["git", "add", ".github/workflows/claude.yml"])
    diff = run(["git", "diff", "--cached", "--quiet"])
    if diff.returncode != 0:
        commit = run(["git", "commit", "-m", "Increase BEM-934 structured binding turn budget"])
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
    receipt.update({
        "status": "PASS",
        "source_commit_sha": head.stdout.strip() if head.returncode == 0 else None,
        "previous_failure": {
            "claude_run_id": 27738266739,
            "run_number": 2559,
            "subtype": "error_max_turns",
            "previous_max_turns": 10,
        },
        "new_max_turns": 30,
    })
    receipt.pop("blocker", None)
    write(receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
