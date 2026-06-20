#!/usr/bin/env python3
"""BEM-949 P1 repository-wide static validation for GitHub Actions workflows.

The runner validates YAML syntax and Python heredoc syntax. Python heredoc bodies
are dedented before compile(), because YAML block scalar indentation is not part
of the embedded Python source at runtime.
"""

from __future__ import annotations

import argparse
import json
import re
import texwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = ROOT / ".github" / "workflows"
DEFAULT_OUT = ROOT / "governance" / "proofs" / "BEM949_p1_ci_static_validation.json"

HEREDOC_RE = re.compile(
    r"(?my)^[ \t]*(?:python|python3)[ \t]+-[ \t]*<<[ \t]*['\"]?"
    r"(?P<tag>[A-Za-z_][A-Za-z0-9_]*)['\"]?[^\n]*\n"
    r"(?P<body>.*?)"
    r"^[ \t]*(?P=tag)[ \t]*$"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def workflow_paths() -> list[Path]:
    return sorted(
        set(WORKFLOWS_DIR.glob("*.yml")) | set(WORKFLOWS_DIR.glob("*.yaml")),
        key=lambda item: item.name,
    )


def validate_workflow(path: Path) -> dict[str, Any]:
    record: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "yaml_valid": False,
        "python_heredocs": 0,
        "python_heredocs_compiled": 0,
        "valid": False,
        "errors": [],
    }
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        record["errors"].append({"kind": "read", "message": str(exc)})
        return record

    try:
        yaml.safe_load(source)
        record["yaml_valid"] = True
    except yaml.YAMLError as exc:
        record["errors"].append({"kind": "yaml", "message": str(exc)})

    for index, match in enumerate(HEREDOC_RE.finditer(source), start=1):
        record["python_heredocs"] += 1
        body = textwrap.dedent(match.group("body"))
        try:
            compile(body, f"{path.name}:heredoc:{index}", "exec")
            record["python_heredocs_compiled"] += 1
        except SyntaxError as exc:
            record["errors"].append(
                {
                    "kind": "python_heredoc",
                    "index": index,
                    "tag": match.group("tag"),
                    "message": f"{exc.msg} at line {exc.lineno}, column {exc.offset}",
                }
            )

    record["valid"] = (
        record["yaml_valid"]
        and record["python_heredocs"] == record["python_heredocs_compiled"]
    )
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    workflows = [validate_workflow(path) for path in workflow_paths()]
    invalid = [item["path"] for item in workflows if not item["valid"]]
    payload = {
        "schema_version": 2,
        "protocol": "BEM-949",
        "task_id": "BEM949-P1-CI-STABILIZE",
        "receipt_id": "BEM949_p1_ci_static_validation",
        "created_at": utc_now(),
        "validator": {
            "path": "scripts/bem949_ci_stabilize.py",
            "heredoc_dedent_before_compile": True,
            "scope": "yaml.safe_load plus Python heredoc compile only",
        },
        "status": "PASS" if not invalid else "FAIL",
        "scope": (
            "Repository-wide static validation only. A static PASS does not claim "
            "manual-dispatch execution for each workflow."
        ),
        "workflow_count": len(workflows),
        "valid_workflow_count": len(workflows) - len(invalid),
        "invalid_workflow_count": len(invalid),
        "invalid_workflows": invalid,
        "workflows": workflows,
        "checks": {
            "all_workflow_files_enumerated": bool(workflows),
            "yaml_safe_load_attempted_for_every_workflow": True,
            "python_heredocs_dedented_before_compile": True,
            "python_heredocs_compiled_for_every_detected_block": True,
            "manual_dispatch_execution_evidence_collected": False,
        },
        "next_action": (
            "Repair only actual YAML or dedented-Python findings, then collect "
            "run-level dispatch evidence for the classified active workflow set."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"BEM949 static validation: {payload['valid_workflow_count']}/"
        f"{payload['workflow_count']} valid; report={args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
