#!/usr/bin/env python3
"""BEM-934 request-driven repository actions executed by GitHub-hosted runner."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REQUEST = ROOT / "governance/runtime/bem934_state_request.json"
PROOFS = ROOT / "governance/proofs"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_receipt(name: str, payload: dict[str, Any]) -> Path:
    PROOFS.mkdir(parents=True, exist_ok=True)
    path = PROOFS / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def deprecate_selfhosted() -> None:
    marker = "# DEPRECATED: requires self-hosted runner, operator will never provide one. See BEM-934."
    targets = [
        ROOT / ".github/workflows/codex-local.yml",
        ROOT / ".github/workflows/codex-local-assembled.yml",
    ]
    changed: list[str] = []
    checks: dict[str, Any] = {}
    for path in targets:
        text = path.read_text(encoding="utf-8")
        if not text.startswith(marker):
            path.write_text(marker + "\n" + text, encoding="utf-8")
            changed.append(str(path.relative_to(ROOT)))
        updated = path.read_text(encoding="utf-8")
        checks[str(path.relative_to(ROOT))] = {
            "deprecated_marker": updated.startswith(marker),
            "historical_file_retained": path.exists(),
        }
    status = "PASS" if all(
        item["deprecated_marker"] and item["historical_file_retained"]
        for item in checks.values()
    ) else "BLOCKED"
    write_receipt(
        "BEM934_deprecate_selfhosted_receipt.json",
        {
            "status": status,
            "protocol": "BEM-934",
            "task_id": "BEM934-DEPRECATE-SELFHOSTED",
            "created_at": utc_now(),
            "checks": checks,
            "changed_files": changed,
            "active_target_policy": "FORBID_NEW_REFERENCES_TO_CODEX_LOCAL",
        },
    )
    if status != "PASS":
        raise SystemExit(1)


ACTIONS = {
    "deprecate_selfhosted": deprecate_selfhosted,
}


def main() -> int:
    request = json.loads(REQUEST.read_text(encoding="utf-8"))
    action = str(request.get("action") or "").strip()
    if not action:
        return 0
    handler = ACTIONS.get(action)
    if handler is None:
        raise SystemExit(f"unsupported BEM-934 action: {action}")
    handler()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
