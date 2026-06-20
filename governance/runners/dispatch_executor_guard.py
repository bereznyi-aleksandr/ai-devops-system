#!/usr/bin/env python3
"""Fail-closed launcher for the BEM-948 dispatch executor.

The underlying executor supports a trace filter; this launcher makes that filter
mandatory so an E2E job cannot replay unrelated planned records.
"""
from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "governance" / "runners" / "dispatch_executor.py"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--max", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    trace = args.trace_id.strip()
    if not trace:
        raise SystemExit("trace_id_required")
    sys.argv = [str(TARGET), "--trace-id", trace, "--max", str(max(1, args.max))]
    if args.dry_run:
        sys.argv.append("--dry-run")
    runpy.run_path(str(TARGET), run_name="__main__")


if __name__ == "__main__":
    main()
