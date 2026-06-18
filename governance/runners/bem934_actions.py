#!/usr/bin/env python3
"""Repair BEM-934 materializer execution_file handling to fail closed."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REQUEST = ROOT / "governance/runtime/bem934_state_request.json"
WORKFLOW = ROOT / ".github/workflows/claude.yml"
RECEIPT = ROOT / "governance/proofs/BEM934_materializer_execution_file_repair_receipt.json"

OLD_PATH = '          execution_path = Path(os.environ.get("EXECUTION_FILE", ""))'
NEW_PATH = (
    '          execution_raw = os.environ.get("EXECUTION_FILE", "").strip()\n'
    '          execution_path = Path(execution_raw) if execution_raw else None'
)
OLD_AVAILABLE = '              "execution_file_available": execution_path.exists(),'
NEW_AVAILABLE = '              "execution_file_available": bool(execution_path and execution_path.is_file()),'
OLD_CHECK = '          if not execution_path.exists():'
NEW_CHECK = '          if execution_path is None or not execution_path.is_file():'


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
        "task_id": "BEM934-MATERIALIZER-EXECUTION-FILE-REPAIR",
        "created_at": now(),
        "action": action,
        "checks": {},
        "missing": [],
    }
    if action != "repair_materializer_execution_file":
        receipt["blocker"] = "unsupported_action"
        write(receipt)
        return 0

    pull = run(["git", "pull", "--rebase", "--autostash", "origin", "main"])
    if pull.returncode != 0:
        receipt["blocker"] = "git_pull_failed"
        receipt["stderr"] = pull.stderr[-2000:]
        write(receipt)
        return 0

    source = WORKFLOW.read_text(encoding="utf-8")
    changed = False
    replacements = (
        (OLD_PATH, NEW_PATH),
        (OLD_AVAILABLE, NEW_AVAILABLE),
        (OLD_CHECK, NEW_CHECK),
    )
    for old, new in replacements:
        if old in source:
            source = source.replace(old, new, 1)
            changed = True
    if changed:
        WORKFLOW.write_text(source, encoding="utf-8")

    updated = WORKFLOW.read_text(encoding="utf-8")
    checks = {
        "execution_raw_guard_present": NEW_PATH in updated,
        "is_file_availability_check_present": NEW_AVAILABLE in updated,
        "fail_closed_missing_file_check_present": NEW_CHECK in updated,
        "unsafe_empty_path_constructor_absent": OLD_PATH not in updated,
        "materializer_step_still_present": "Materialize BEM-934 binding plan from Claude result" in updated,
    }
    receipt["checks"] = checks
    receipt["missing"] = [k for k, v in checks.items() if not v]
    receipt["changed"] = changed
    if receipt["missing"]:
        receipt["blocker"] = "execution_file_repair_validation_failed"
        write(receipt)
        return 0

    run(["git", "config", "user.email", "bem934-repair@ai-devops-system"])
    run(["git", "config", "user.name", "BEM-934 Repair"])
    run(["git", "add", ".github/workflows/claude.yml"])
    diff = run(["git", "diff", "--cached", "--quiet"])
    if diff.returncode != 0:
        commit = run(["git", "commit", "-m", "Fail close BEM-934 materializer execution_file handling"])
        if commit.returncode != 0:
            receipt["blocker"] = "git_commit_failed"
            receipt["stderr"] = commit.stderr[-2000:]
            write(receipt)
            return 0
        push = run(["git", "push"])
        if push.returncode != 0:
            pull2 = run(["git", "pull", "--rebase", "origin", "main"])
            push2 = run(["git", "push"]) if pull2.returncode == 0 else pull2
            if pull2.returncode != 0 or push2.returncode != 0:
                receipt["blocker"] = "git_push_failed"
                receipt["stderr"] = (pull2.stderr + "\n" + push2.stderr)[-3000:]
                write(receipt)
                return 0

    head = run(["git", "rev-parse", "HEAD"])
    receipt.update({
        "status": "PASS",
        "source_commit_sha": head.stdout.strip() if head.returncode == 0 else None,
        "workflow_path": ".github/workflows/claude.yml",
    })
    receipt.pop("blocker", None)
    write(receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
