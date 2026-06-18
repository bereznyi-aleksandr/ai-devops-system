#!/usr/bin/env python3
"""Repair claude.yml to pass assembled prompt content through the supported prompt input."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REQUEST = ROOT / "governance/runtime/bem934_state_request.json"
WORKFLOW = ROOT / ".github/workflows/claude.yml"
RECEIPT = ROOT / "governance/proofs/BEM934_claude_prompt_content_bridge_receipt.json"

RUN_MARKER = "      - name: Run Claude Code role\n"
LOAD_STEP = """      - name: Load assembled prompt content
        id: load_prompt
        if: github.event_name == 'workflow_dispatch'
        shell: bash
        run: |
          set -euo pipefail
          {
            echo 'prompt<<BEM934_PROMPT_EOF'
            cat "$PROMPT_FILE"
            echo 'BEM934_PROMPT_EOF'
          } >> "$GITHUB_OUTPUT"

"""
UNSUPPORTED = "          prompt_file: ${{ env.PROMPT_FILE }}"
SUPPORTED = "          prompt: ${{ steps.load_prompt.outputs.prompt }}"

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
        "task_id": "BEM934-CLAUDE-PROMPT-CONTENT-BRIDGE",
        "created_at": now(),
        "action": action,
        "checks": {},
        "missing": [],
    }
    if action != "repair_claude_prompt_content_bridge":
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
    if "id: load_prompt\n" not in source:
        if RUN_MARKER not in source:
            receipt["blocker"] = "claude_role_marker_missing"
            write(receipt)
            return 0
        source = source.replace(RUN_MARKER, LOAD_STEP + RUN_MARKER, 1)
        changed = True

    unsupported_count = source.count(UNSUPPORTED)
    if unsupported_count:
        source = source.replace(UNSUPPORTED, SUPPORTED)
        changed = True

    WORKFLOW.write_text(source, encoding="utf-8")
    updated = WORKFLOW.read_text(encoding="utf-8")
    checks = {
        "load_prompt_step_present": "id: load_prompt\n" in updated,
        "assembled_prompt_file_read": 'cat "$PROMPT_FILE"' in updated,
        "multiline_github_output_used": "prompt<<BEM934_PROMPT_EOF" in updated,
        "supported_prompt_input_used_by_roles": updated.count(SUPPORTED) >= 2,
        "unsupported_prompt_file_input_absent": "prompt_file:" not in updated,
        "structured_binding_role_preserved": "id: claude_binding_role\n" in updated,
        "structured_output_materializer_preserved": "outputs.structured_output" in updated,
    }
    receipt["checks"] = checks
    receipt["missing"] = [key for key, value in checks.items() if not value]
    receipt["changed"] = changed
    receipt["unsupported_inputs_replaced"] = unsupported_count
    if receipt["missing"]:
        receipt["blocker"] = "prompt_content_bridge_validation_failed"
        write(receipt)
        return 0

    run(["git", "config", "user.email", "bem934-prompt-content@ai-devops-system"])
    run(["git", "config", "user.name", "BEM-934 Prompt Content Bridge"])
    run(["git", "add", ".github/workflows/claude.yml"])
    diff = run(["git", "diff", "--cached", "--quiet"])
    if diff.returncode != 0:
        commit = run(["git", "commit", "-m", "Fix BEM-934 Claude assembled prompt content bridge"])
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
        "official_input": "prompt",
        "unsupported_input_removed": "prompt_file",
    })
    receipt.pop("blocker", None)
    write(receipt)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
