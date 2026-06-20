#!/usr/bin/env python3
"""Validate the BEM949 active control-plane workflow scope.

This is a scoped static validation and intentionally does not claim that historical
BEM-934/BEM-947/BEM-948 archival workflows are operational. It preserves that boundary.in the receipt.
"""

import json
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / "governance" / "registry" / "BEM949_WORKFLOW_OPERABILITY_SCOPE.json"
OUT = ROOT / "governance" / "proofs" / "BEM949_p1_active_scope_static_validation.json"

HEREDOC = re.compile(
    r"(?ms)^[ \t]*(?:python|python3)[ \t]+-[ \t]*<<[ \t]*['\"]?"
    r"(?P<tag>[A-Za-z_][A-Za-z0-9_]*)['\"]?[^\n]*\n"
    r"(?P<body>.*?)"
    r"^[ \t]*(?P=tag)[ \t]*$"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate(relative_path: str) -> dict:
    path = ROOT / relative_path
    record = {
        "path": relative_path,
        "exists": path.is_file(),
        "yaml_valid": False,
        "python_heredocs": 0,
        "python_heredocs_compiled": 0,
        "valid": False,
        "errors": [],
    }
    if not path.is_file():
        record["errors"].append({"kind": "file", "message": "file missing"})
        return record
    source = path.read_text(encoding="utf-8")
    try:
        yaml.safe_load(source)
        record["yaml_valid"] = True
    except yaml.YAMLError as exc:
        record["errors"].append({"kind": "yaml", "message": str(exc)})

    for index, match in enumerate(HEREDOC.finditer(source), start=1):
        record["python_heredocs"] += 1
        try:
            compile(textwrap.dedent(match.group("body")), f"{relative_path}:heredoc:{index}", "exec")
            record["python_heredocs_compiled"] += 1
        except SyntaxError as exc:
            record["errors"].append({
                "kind": "python_heredoc",
                "index": index,
                "message": f"{exc.msg} at line {exc.lineno}, column {exc.offset}",
            })
    record["valid"] = (
        record["yaml_valid"] and record["python_heredocs"] == record["python_heredocs_compiled"]
    )
    return record


def main() -> int:
    scope = json.loads(SCOPE.read_text(encoding="utf-8"))
    workflows = [
        validate(str(item["path"]))
        for item in scope["active_control_plane_workflows"]
    ]
    invalid = [row["path"] for row in workflows if not row["valid"]]
    payload = {
        "schema_version": 1,
        "protocol": "BEM-949",
        "task_id": "BEM949-P1-CI-STABILIZE",
        "receipt_id": "BEM949_p1_active_scope_static_validation",
        "created_at": utc_now(),
        "scope_registry": "governance/registry/BEM949_WORKFLOW_OPERABILITY_SCOPE.json",
        "status": "PASS" if not invalid else "FAIL",
        "workflow_count": len(workflows),
        "valid_workflow_count": len(workflows) - len(invalid),
        "invalid_workflows": invalid,
        "workflows": workflows,
        "checks": {
            "active_workflow_files_enumerated": True,
            "yaml_safe_load_attempted_for_active_workflows": True,
            "python_heredocs_dedented_before_compile": True,
            "per_active_workflow_run_evidence_collected": False,
            "legacy_workflows_excluded_from_active_scope": True,
        },
        "non_claim": (
            "Static PASS for this explicit active scope does not claim per-workflow 