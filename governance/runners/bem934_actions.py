#!/usr/bin/env python3
"""BEM-934 repair for Claude prompt-file bridge."""
from __future__ import annotations
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REQUEST = ROOT / "governance/runtime/bem934_state_request.json"
WORKFLOW = ROOT / ".github/workflows/claude.yml"
RECEIPT = ROOT / "governance/proofs/BEM934_claude_prompt_file_bridge_receipt.json"

OLD = "prompt: ${{ env.PROMPT_FILE && format('{0}', env.PROMPT_FILE) }}"
NEW = "prompt_file: ${{ env.PROMPT_FILE }}"

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
        "task_id": "BEM934-CLAUDE-PROMPT-FILE-BRIDGE-REPAIR",
        "created_at": now(),
        "action": action,
        "checks": {},
        "missing": [],
    }
    if action != "repair_claude_prompt_file":
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
        "prompt_file_input_present": NEW in updated,
        "path_passed_as_prompt_absent": OLD not in updated,
        "assembled_prompt_env_present": "ASSEMBLED_ROLE_PROMPT" in updated and "PROMPT_FILE" in updated,
    }
    receipt["checks"] = checks
    receipt["missing"] = [key for key, value in checks.items() if not value]
    receipt["changed"] = old_present

    if not all(checks.values()):
        receipt["blocker"] = "claude_prompt_file_bridge_validation_failed"
        write(receipt)
        return 0

    run(["git", "config", "user.email", "bem934-repair@ai-devops-system"])
    run(["git", "config", "user.name", "BEM-934 Repair"])
    run(["git", "add", ".github/workflows/claude.yml"])
    diff = run(["git", "diff", "--cached", "--quiet"])
    commit_sha = None
    if diff.returncode != 0:
        commit = run(["git", "commit", "-m", "Fix BEM-934 Claude prompt_file bridge"])
        if commit.returncode != 0:
            receipt["blocker"] = "git_commit_failed"
            receipt["git_commit_stderr"] = commit.stderr[-2000:]
            write(receipt)
            return 0
        push = run(["git", "push"])
        if push.returncode != 0:
            retry_pull = run(["git", "pull", "--rebase", "origin", "main"])
            retry_push = run(["git", "push"]) if retry_pull.returncode == 0 else retry_pull
            if retry_pull.returncode != 0 or retry_push.returncode != 0:
                receipt["blocker"] = "git_push_failed"
                receipt["git_push_stderr"] = (retry_pull.stderr + "\n" + retry_push.stderr)[-3000:]
                write(receipt)
                return 0
        head = run(["git", "rev-parse", "HEAD"])
        commit_sha = head.stdout.strip() if head.returncode == 0 else None
    else:
        head = run(["git", "rev-parse", "HEAD"])
        commit_sha = head.stdout.strip() if head.returncode == 0 else None

    receipt.update({
        "status": "PASS",
        "source_commit_sha": commit_sha,
        "workflow_path": ".github/workflows/claude.yml",
        "official_action_contract": "anthropics/claude-code-action@v1 prompt_file input",
    })
    receipt.pop("blocker", None)
    write(receipt)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
