#!/usr/bin/env python3
"""BEM-934 repair: allow the Claude automation role to write and commit proof files."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REQUEST = ROOT / "governance/runtime/bem934_state_request.json"
WORKFLOW = ROOT / ".github/workflows/claude.yml"
RECEIPT = ROOT / "governance/proofs/BEM934_claude_write_tools_receipt.json"

OLD = "          claude_args: --max-turns 10"
NEW = "          claude_args: '--max-turns 10 --allowedTools \"Edit,Read,Write,Glob,Grep,Bash(git:*)\"'"

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)

def write(payload: dict[str, Any]) -> None:
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def main() -> int:
    request = json.loads(REQUEST.read_text(encoding="utf-8"))
    action = str(request.get("action") or "")
    receipt: dict[str, Any] = {
        "status": "BLOCKED",
        "protocol": "BEM-934",
        "task_id": "BEM934-CLAUDE-WRITE-TOOLS-REPAIR",
        "created_at": now(),
        "action": action,
        "checks": {},
        "missing": [],
    }
    if action != "repair_claude_write_tools":
        receipt["blocker"] = "unsupported_action"
        write(receipt)
        return 0

    pull = run(["git", "pull", "--rebase", "--autostash", "origin", "main"])
    if pull.returncode != 0:
        receipt["blocker"] = "git_pull_failed"
        receipt["git_pull_stderr"] = pull.stderr[-2000:]
        write(receipt)
        return 0

    source = WORKFLOW.read_text(encoding="utf-8")
    old_present = OLD in source
    if old_present:
        source = source.replace(OLD, NEW, 1)
        WORKFLOW.write_text(source, encoding="utf-8")

    updated = WORKFLOW.read_text(encoding="utf-8")
    checks = {
        "claude_action_v1_present": "uses: anthropics/claude-code-action@v1" in updated,
        "prompt_file_input_present": "prompt_file: ${{ env.PROMPT_FILE }}" in updated,
        "write_tools_explicitly_allowed": NEW in updated,
        "legacy_unrestricted_replacement_not_applied": updated.count(NEW) == 1,
        "old_primary_claude_args_absent": OLD not in updated.split("Run Claude Code legacy", 1)[0],
    }
    receipt["checks"] = checks
    receipt["missing"] = [key for key, value in checks.items() if not value]
    receipt["changed"] = old_present
    if not all(checks.values()):
        receipt["blocker"] = "claude_write_tools_validation_failed"
        write(receipt)
        return 0

    run(["git", "config", "user.email", "bem934-repair@ai-devops-system"])
    run(["git", "config", "user.name", "BEM-934 Repair"])
    run(["git", "add", ".github/workflows/claude.yml"])
    diff = run(["git", "diff", "--cached", "--quiet"])
    commit_sha = None
    if diff.returncode != 0:
        commit = run(["git", "commit", "-m", "Allow BEM-934 Claude proof write tools"])
        if commit.returncode != 0:
            receipt["blocker"] = "git_commit_failed"
            receipt["git_commit_stderr"] = commit.stderr[-2000:]
            write(receipt)
            return 0
        push = run(["git", "push"])
        if push.returncode != 0:
            pull2 = run(["git", "pull", "--rebase", "origin", "main"])
            push2 = run(["git", "push"]) if pull2.returncode == 0 else pull2
            if pull2.returncode != 0 or push2.returncode != 0:
                receipt["blocker"] = "git_push_failed"
                receipt["git_push_stderr"] = (pull2.stderr + "\n" + push2.stder)[-3000:]
                write(receipt)
                return 0
    head = run(["git", "rev-parse", "HEAD"])
    commit_sha = head.stdout.strip() if head.returncode == 0 else None
    receipt.update({
        "status": "PASS",
        "source_commit_sha": commit_sha,
        "workflow_path": ".github/workflows/claude.yml",
        "allowed_tools": ["Edit", "Read", "Write", "Glob", "Grep", "Bash(git:*)"],
    })
    receipt.pop("blocker", None)
    write(receipt)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
