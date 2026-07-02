#!/usr/bin/env python3
"""BEM-949 DSM-1 dispatch lifecycle executor.

DISPATCHED is only acknowledgement. A run is terminal only after the GitHub
Actions API exposes its run_id and a completed conclusion. Every observed
transition is appended to an auditable lifecycle log.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DEFAULT = ROOT / "governance/state/dispatch_processed.jsonl"
EXECUTED_DEFAULT = ROOT / "governance/state/dispatch_executed.jsonl"
LIFECYCLE_DEFAULT = ROOT / "governance/state/dispatch_lifecycle.jsonl"
RECEIPT_DEFAULT = ROOT / "governance/proofs/BEM948_dispatch_executor_receipt.json"
TARGETS = {"claude_code": "claude.yml", "gpt_codex_cloud": "gpt-codex-cloud.yml"}

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def rows(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            out.append(value)
    return out

def append(path: Path, values: list[dict[str, Any]]) -> None:
    if not values:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for value in values:
            fh.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")

def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def key(row: dict[str, Any]) -> str:
    return str(row.get("dispatch_id") or row.get("race_id") or "")
