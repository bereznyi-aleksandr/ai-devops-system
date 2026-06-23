#!/usr/bin/env python3
"""Write independent static validation evidence for BEM-931 RM04 runners."""

import argparse
import ast
import hashlib
import json
import py_compile
from datetime import datetime, timezone
from pathlib import Path

RUNNERS = (
    "governance/runners/gd_curator_runner.py",
    "governance/runners/dir_curator_runner.py",
    "governance/runners/wrk_curator_runner.py",
    "governance/runners/analyst_stage_runner.py",
    "governance/runners/auditor_stage_runner.py",
    "governance/runners/executor_stage_runner.py",
)


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def has_main(source, path):
    tree = ast.parse(source, filename=str(path))
    return any(isinstance(node, ast.FunctionDef) and node.name == "main" for node in tree.body)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="governance/proofs/BEM931-V36-RM04_runners_receipt.json")
    args = parser.parse_args()

    checked = []
    for item in RUNNERS:
        path = Path(item)
        if not path.is_file():
            raise FileNotFoundError(str(path))
        py_compile.compile(str(path), doraise=True)
        source = path.read_text(encoding="utf-8")
        if not has_main(source, path):
            raise ValueError("missing main(): {0}".format(path))
        checked.append(
            {
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "sha_type": "sha256_content",
                "python_compiled": True,
                "has_main": True,
            }
        )

    receipt = {
        "schema_version": 1,
        "protocol": "BEM-931 v3.6",
        "roadmap_item": "RM-04-RUNNERS",
        "receipt_type": "static_runner_validation",
        "status": "PASS",
        "created_at": now(),
        "checked_runners": checked,
        "non_claim": "This receipt establishes Python compilation and main() entrypoints only; it does not establish live provider dispatch.",
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(recipt, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
