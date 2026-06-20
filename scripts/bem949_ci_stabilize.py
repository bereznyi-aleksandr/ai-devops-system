#!/usr/bin/env python3
"""BEM-949 P1 static workflow validator."""
import argparse
import json
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WFDIR = ROOT / ".github" / "workflows"
DEFAULT_OUT = ROOT / "governance" / "proofs" / "BEM949_p1_ci_static_validation.json"
HEREDOC = re.compile(
    r"(?ms)^[ \t]*(?:python|python3)[ \t]+-[ \t]*<<[ \t]*['\"]?"
    r"(?P<tag>[A-Za-z_][A-Za-z0-9_]*)['\"]?[^\n]*\n"
    r"(?P<body>.*?)"
    r"^[ \t]*(?P=tag)[ \t]*$"
)

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def validate(path: Path) -> dict:
    item = {
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
        item["errors"].append({"kind": "read", "message": str(exc)})
        return item
    try:
        yaml.safe_load(source)
        item["yaml_valid"] = True
    except yaml.YAMLError as exc:
        item["errors"].append({"kind": "yaml", "message": str(exc)})
    for idx, match in enumerate(HEREDOC.finditer(source), 1):
        item["python_heredocs"] += 1
        try:
            compile(textwrap.dedent(match.group("body")), f"{path.name}:heredoc:{idx}", "exec")
            item["python_heredocs_compiled"] += 1
        except SyntaxError as exc:
            item["errors"].append({
                "kind": "python_heredoc",
                "index": idx,
                "tag": match.group("tag"),
                "message": f"{exc.msg} at line {exc.lineno}, column {exc.offset}",
            })
    item["valid"] = item["yaml_valid"] and item["python_heredocs"] == item["python_heredocs_compiled"]
    return item

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    paths = sorted(set(WFDIR.glob("*.yml")) | set(WFDIR.glob("*.yaml")), key=lambda p: p.name)
    workflows = [validate(path) for path in paths]
    invalid = [item["path"] for item in workflows if not item["valid"]]
    payload = {
        "schema_version": 2,
        "protocol": "BEM-949",
        "task_id": "BEM949-P1-CI-STABILIZE",
        "receipt_id": "BEM949_p1_ci_static_validation",
        "created_at": now(),
        "validator": {
            "path": "scripts/bem949_ci_stabilize.py",
            "heredoc_dedent_before_compile": True,
            "scope": "yaml.safe_load plus Python heredoc compile only",
        },
        "status": "PASS" if not invalid else "FAIL",
        "scope": "Repository-wide static validation only; no per-workflow execution claim.",
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
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"BEM949 static validation: {payload['valid_workflow_count']}/{payload['workflow_count']} valid")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
