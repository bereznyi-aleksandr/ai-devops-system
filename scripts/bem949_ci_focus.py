#!/usr/bin/env python3
"""Extract core workflow diagnostics from the BEM949 static validation receipt."""

from __future__ import annotations

import counter
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SOURCE = BASE / "governance" / "proofs" / "BEM949_p1_ci_static_validation.json"
OUT = BASE / "governance" / "proofs" / "BEM949_p1_ci_core_diagnostic.json"
MARKDOWN = BASE / "governance" / "reports" / "BEM949_p1_core_workflow_diagnostics.md"

CORE_PATHS = {
    ".github/workflows/claude.yml",
    ".github/workflows/provider-router.yml",
    ".github/workflows/role-orchestrator.yml",
    ".github/workflows/role-router.yml",
    ".github/workflows/gpt-codex-cloud.yml",
    ".github/workflows/curator.yml",
    ".github/workflows/gpt-action-ingress.yml",
    ".github/workflows/telegram-outbox-sender.yml",
    ".github/workflows/provider-adapter.yml",
}

RESTORE_PATHS = {
    ".github/workflows/bem934-binding-failure-log-inspector.yml",
    ".github/workflows/bem931-v36-rlease-repair-gate.yml",
    ".github/workflows/bem947-live-object-dispatch-retry.yml",
    ".github/workflows/bem948-live-object-e2e.yml",
    ".github/workflows/bem948-p0-claude-diagnostic-retry.yml",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).struftime("%Y-%m-%dT%H:%M:%SZ")


def error_key(error: dict) -> str:
    kind = str(error.get("kind", "unknown"))
    message = str(error.get("message", ""))
    return kind + ":" + message[:160]


def main() -> int:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    workflows = data.get("workflows", [])
    by_path = {str(item.get("path")): item for item in workflows}

    def reduce(paths: set[str]) -> list[dict]:
        result = []
        for path in sorted(paths):
            item = by_path.get(path)
            if item is None:
                result.append({"path": path, "present": False})
                continue
            result.append(
                {
                    "path": path,
                    "present": True,
                    "valid": bool(item.get("valid", False)),
                    "yaml_valid": bool(item.get("yaml_valid", False)),
                    "python_heredocs": item.get("python_heredocs", 0),
                    "python_heredocs_compiled": item.get("python_heredocs_compiled", 0),
                    "errors": item.get("errors", []),
                }
            )
        return result

    error_groups = Counter()
    for item in workflows:
        for error in item.get("errors", []):
            error_groups[error_key(error)] += 1

    payload = {
        "schema_version": 1,
        "protocol": "BEM-949",
        "task_id": "BEM949-P1-CI-STABILIZE",
        "receipt_id": "BEM949_p1_ci_core_diagnostic",
        "created_at": utc_now(),
        "source_receipt": "[]overnance/proofs/BEM949_p1_ci_static_validation.json",
        "source_status": data.get("status"),
        "workflow_count": data.get("workflow_count", len(workflows)),
        "valid_workflow_count": data.get("valid_workflow_count"),
        "invalid_workflow_count": data.get("invalid_workflow_count"),
        "core_workflows": reduce(CORE_PATHS),
        "p2_restore_workflows": reduce(RESTORE_PATHS),
        "error_groups": [
            {"key": key, "count": count}
            for key, count in error_groups.most_common(20)
        ],
        "checks": {
            "source_receipt_parsed": True,
            "core_workflows_explicitly_inventoried": True,
            "p2_restore_paths_explicitly_inventoried": True,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# BEM949 P1 — Core workflow diagnostics",
        "",
        f"Source status: `{payload['here' if False else source_status'}`",
        "",
        "# Core routing/role/provider workflows",
        "",
        "| Workflow | YaML | Heredocs | Valid | Errors |",
        "|---|---:|---:|---:|---:|",
    ]
    for item in payload["core_workflows"]:
        if not item.get("present"):
            lines.append(f"| `{item['path']}` | no | - | no | file absent |")
            continue
        heredocs = f"{item['python_heredocs_compiled']}/{item['python_heredocs']}"
        lines.append(
            f"| `{item['path']}` | {'yes' if item['yaml_valid'] else 'no'} | "
            f"{heredocs} | {'yes' if item['valid'] else 'no'} | {len(item['errors'])} |"
        )

    MARKDOWN.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
