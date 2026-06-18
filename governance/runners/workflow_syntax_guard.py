#!/usr/bin/env python3
"""BEM-937 workflow syntax guard.

This guard is intentionally conservative: it verifies that legacy workflows
known to have failed in GitHub UI were replaced with short valid manual guards
and no longer contain inline heredoc Python blocks that previously broke YAML.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROOFS = ROOT / "governance" / "proofs"
TARGETS = [
    ".github/workflows/bem934-finalize-real-telegram-live-test.yml",
    ".github/workflows/bem934-claude-action-input-diagnostic.yml",
    ".github/workflows/bem934-live-trace-monitor.yml",
    ".github/workflows/bem934-objects-runtime-binding.yml",
    ".github/workflows/bem934-fix-claude-live-outcome.yml",
    ".github/workflows/bem934-stage-runner-smoke.yml",
    ".github/workflows/bem934-v2-binding-inspector.yml",
    ".github/workflows/bem934-deprecate-selfhosted.yml",
]


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def check_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    return {
        "path": str(path.relative_to(ROOT)),
        "exists": path.exists(),
        "has_workflow_dispatch": "workflow_dispatch:" in text,
        "has_runs_on": "runs-on: ubuntu-latest" in text,
        "has_legacy_guard": "Legacy workflow syntax guard" in text,
        "no_inline_python_heredoc": "<<'PY'" not in text and '<<"PY"' not in text,
        "no_write_permission": "contents: write" not in text,
    }


def main() -> None:
    checked = [check_file(ROOT / item) for item in TARGETS]
    checks = {
        "all_targets_present": all(item["exists"] for item in checked),
        "all_dispatchable": all(item["has_workflow_dispatch"] for item in checked),
        "all_have_runner": all(item["has_runs_on"] for item in checked),
        "all_guarded": all(item["has_legacy_guard"] for item in checked),
        "inline_python_heredocs_removed": all(item["no_inline_python_heredoc"] for item in checked),
        "legacy_release_write_disabled": all(item["no_write_permission"] for item in checked),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    receipt = {
        "status": "PASS" if not blockers else "BLOCKED",
        "protocol": "BEM-937",
        "task_id": "BEM937-P0-LEGACY-WORKFLOW-SYNTAX-REPAIR",
        "created_at": now(),
        "stage": {"tasks_done": 1, "tasks_total": 4, "percent": 25},
        "targets": checked,
        "checks": checks,
        "blockers": blockers,
        "next_task": "BEM937-P1-WORKFLOW-SYNTAX-GUARD" if not blockers else None,
    }
    PROOFS.mkdir(parents=True, exist_ok=True)
    out = PROOFS / "BEM937_legacy_workflow_syntax_repair_receipt.json"
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if blockers:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
