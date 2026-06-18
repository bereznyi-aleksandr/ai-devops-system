#!/usr/bin/env python3
"""Repair the BEM-934 GitHub output delimiter and record proof."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REQUEST = ROOT / "governance/runtime/bem934_state_request.json"
WORKFLOW = ROOT / ".github/workflows/claude.yml"
RECEIPT = ROOT / "governance/proofs/BEM934_prompt_output_delimiter_repair_receipt.json"

OLD = "            echo 'BEM934_PROMPT_EOF'\n"
NEW = "            printf '\\nBEM934_PROMPT_EOF\\n'\n"

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
        "task_id": "BEM934-PROMPT-OUTPUT-DELIMITER-REPAIR",
        "created_at": now(),
        "action": action,
        "checks": {},
        "missing": [],
    }
    if action != "repair_prompt_output_delimiter":
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
    old_count = source.count(OLD)
    if old_count:
        source = source.replace(OLD, NEW, 1)
        WORKFLOW.write_text(source, encoding="utf-8")

    updated = WORKFLOW.read_text(encoding="utf-8")
    checks = {
        "load_prompt_step_present": "id: load_prompt\n" in updated,
        "prompt_file_is_read": 'cat "$PROMPT_FILE"' in updated,
        "delimiter_header_present": "echo 'prompt<<BEM934_PROMPT_EOF'" in updated,
        "delimiter_forced_to_new_line": NEW in updated,
        "unsafe_echo_delimiter_absent": OLD not in updated,
        "official_prompt_input_present": "prompt: ${{ steps.load_prompt.outputs.prompt }}" in updated,
    }
    receipt["checks"] = checks
    receipt["old_occurrences_repaired"] = old_count
    receipt["missing"] = [key for key, value in checks.items() if not value]
    if receipt["missing"]:
        receipt["blocker"] = "delimiter_repair_validation_failed"
        write(receipt)
        return 0

    run(["git", "config", "user.email", "bem934-delimiter@ai-devops-system"])
    run(["git", "config", "user.name", "BEM-934 Delimiter Repair"])
    run(["git", "add", ".github/workflows/claude.yml"])
    diff = run(["git", "diff", "--cached", "--quiet"])
    if diff.returncode != 0:
        commit = run(["git", "commit", "-m", "Fix BEM-934 prompt output delimiter newline"])
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
        "delimiter": "BEM934_PROMPT_EOF",
    })
    receipt.pop("blocker", None)
    write(receipt)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
