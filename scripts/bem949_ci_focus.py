#!/usr/bin/env python3
"""Extract BEM-949 P1 core workflow diagnostics from the full static receipt."""

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "governance" / "proofs" / "BEM949_p1_ci_static_validation.json"
OUT = ROOT / "governance" / "proofs" / "BEM949_p1_ci_core_diagnostic.json"
MARKDOWN = ROOT / "governance" / "reports" / "BEM949_p1_core_workflow_diagnostics.md"

CORE_PATHS = (
    ".github/workflows/claude.yml",
    ".github/workflows/provider-router.yml",
    ".github/workflows/role-orchestrator.yml",
    ".github/workflows/role-router.yml",
    ".github/workflows/gpt-codex-cloud.yml",
    ".github/workflows/curator.yml",
    ".github/workflows/gpt-action-ingress.yml",
    ".github/workflows/telegram-outbox-sender.yml",
    ".github/workflows/provider-adapter.yml",
)
RESTORE_PATHS = (
    ".github/workflows/bem934-binding-failure-log-inspector.yml",
    ".github/workflows/bem931-v36-release-repair-gate.yml",
    ".github/workflows/bem947-live-object-dispatch-retry.yml",
    ".github/workflows/bem948-live-object-e2e.yml",
    ".github/workflows/bem948-p0-claude-diagnostic-retry.yml",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compact(item: dict, path: str) -> dict:
    if not item:
        return {"path": path, "present": False}
    return {
        "path": path,
        "present": True,
        "valid": bool(item.get("valid", False)),
        "yaml_valid": bool(item.get("yaml_valid", False)),
        "python_heredocs": int(item.get("python_heredocs", 0)),
        "python_heredocs_compiled": int(item.get("python_heredocs_compiled", 0)),
        "errors": item.get("errors", []),
    }


def error_key(error: dict) -> str:
    message = str(error.get("message", "")).replace("\n", " ")
    return f"{error.get('kind', 'unknown')}: {message[:180]}"


def main() -> int:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    workflows = source.get("workflows", [])
    by_path = {str(item.get("path", "")): item for item in workflows}

    errors = Counter()
    for item in workflows:
        for error in item.get("errors", []):
            errors[error_key(error)] += 1

    core = [compact(by_path.get(path), path) for path in CORE_PATHS]
    restore = [compact(by_path.get(path), path) for path in RESTORE_PATHS]
    payload = {
        "schema_version": 1,
        "protocol": "BEM-949",
        "task_id": "BEM949-P1-CI-STABILIZE",
        "receipt_id": "BEM949_p1_ci_core_diagnostic",
        "created_at": utc_now(),
        "source_receipt": "governance/proofs/BEM949_p1_ci_static_validation.json",
        "source_status": source.get("status"),
        "workflow_count": source.get("workflow_count", len(workflows)),
        "valid_workflow_count": source.get("valid_workflow_count"),
        "invalid_workflow_count": source.get("invalid_workflow_count"),
        "core_workflows": core,
        "p2_restore_workflows": restore,
        "error_groups": [{"key": key, "count": count} for key, count in errors.most_common(20)],
        "checks": {
            "sourceipt_parsed": True,
            "core_workflows_explicitly_inventoried": True,
            "p2_restore_paths_explicitly_inventoried": True,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# BEM-949 P1 — Core workflow diagnostics",
        "",
        f"Source status: `{payload['source_status']}`",
        "",
        "| Workflow | YALL | Heredocs | Valid | Errors |",
        "|---|---:|---:|---:|---:|",
    ]
    for item in core:
        if not item["present"]:
            lines.append(f"| `{item['path']}` | no | - | no | file absent |")
            continue
        heredocs = f"{item['python_heredocs_compiled']}/{item['python_heredocs']}"
        lines.append(
            f"| `{item['path']}` | {'yes' if item['yaml_valid'] else 'no'} | {heredocs} | "
            f"{'yes' if item['valid'] else 'no'} | {len(item['errors'])} |"
        )
    MARKDOWN.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
