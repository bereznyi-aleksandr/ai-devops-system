#!/usr/bin/env python3
"""BEM-949 P1 repository-wide static CI validation.

The checker inventories each workflow under .github/workflows, parses YAML with
yaml.safe_load(), extracts Python heredocs, and compile()s each extracted block.
It always writes a receipt-style JSON report so invalid findings remain available
for repair rather than disappearing behind a failed CI job.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "PyYAML is required. Install it with: python -m pip install PyYAML"
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = ROOT / ".github" / "workflows"
DEFAULT_OUT = ROOT / "governance" / "proofs" / "BEM949_p1_ci_static_validation.json"

HEREDOC_RE = re.compile(
    r"(?ms)^[ \t]*(?:python|python3)[ \t]+-[ \t]*<<[ \t]*['\"]?"
    r"(?P<tag>[A-Za-z_][A-Za-z0-9_]*)['\"]?[^\n]*\n"
    r"(?P<body>.*?)"
    r"^[ \t]*(?P=tag)[ \t]*$"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def workflow_paths() -> list[Path]:
    return sorted(
        {
            *WORKFLOWS_DIR.glob("*.yml"),
            *WORKFLOWS_DIR.glob("*.yaml"),
        },
        key=lambda path: path.name,
    )


def validate_workflow(path: Path) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "yaml_valid": False,
        "python_heredocs": 0,
        "python_heredocs_compiled": 0,
        "valid": False,
        "errors": [],
    }
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        entry["errors"].append({"kind": "read", "message": str(exc)})
        return entry

    try:
        yaml.safe_load(text)
        entry["yaml_valid"] = True
    except yaml.YAMLError as exc:
        entry["errors"].append({"kind": "yaml", "message": str(exc)})

    for index, match in enumerate(HEREDOC_RE.finditer(text), start=1):
        entry["python_heredocs"] += 1
        body = match.group("body")
        try:
            compile(body, f"{path.name}:heredoc:{index}", "exec")
            entry["python_heredocs_compiled"] += 1
        except SyntaxError as exc:
            entry["errors"].append(
                {
                    "kind": "python_heredoc",
                    "index": index,
                    "tag": match.group("tag"),
                    "message": (
                        f"{exc.msg} at line {exc.lineno}, column {exc.offset}"
                    ),
                }
            )

    entry["valid"] = (
        entry["yaml_valid"]
        and entry["python_heredocs"] == entry["python_heredocs_compiled"]
    )
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate BEM-949 GitHub Actions workflow syntax"
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    paths = workflow_paths()
    results = [validate_workflow(path) for path in paths]
    invalid = [item["path"] for item in results if not item["valid"]]

    payload = {
        "schema_version": 1,
        "protocol": "BEM-949",
        "task_id": "BEM949-P1-CI-STABILIZE",
        "receipt_id": "BEM949_p1_ci_static_validation",
        "created_at": utc_now(),
        "status": "PASS" if not invalid else "FAIL",
        "scope": (
            "Repository-wide static validation only: yaml.safe_load() and compile() "
            "for extracted Python heredocs. It is not an executed green-dispatch "
            "claim for the checked workflows."
        ),
        "workflow_count": len(results),
        "valid_workflow_count": len(results) - len(invalid),
        "invalid_workflow_count": len(invalid),
        "invalid_workflows": invalid,
        "workflows": results,
        "checks": {
            "all_workflow_files_enumerated": bool(results),
            "yaml_safe_load_attempted_for_every_workflow": True,
            "python_heredocs_compiled_for_every_detected_block": True,
            "manual_dispatch_execution_evidence_collected": False,
        },
        "next_action": (
            "Repair invalid workflow findings, then collect trace-bound "
            "manual-dispatch completion evidence per active workflow."
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
