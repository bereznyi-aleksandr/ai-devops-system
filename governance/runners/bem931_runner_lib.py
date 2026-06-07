#!/usr/bin/env python3
"""Shared helpers for BEM-931 v3.6 runners."""
import json
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
CHANNELS = ROOT / "governance" / "channels"
RESULTS = ROOT / "governance" / "runtime" / "results"
ARTIFACTS = ROOT / "governance" / "artifacts"

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows

def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

def first_pending(path: Path) -> dict | None:
    for row in read_jsonl(path):
        if row.get("status", "pending") == "pending":
            return row
    return None

def write_result(name: str, payload: dict) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    trace_id = payload.get("trace_id") or f"{name}_{uuid4().hex[:12]}"
    payload = dict(payload)
    payload.setdefault("trace_id", trace_id)
    payload.setdefault("created_at", now_iso())
    payload.setdefault("status", "completed")
    path = RESULTS / f"{trace_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
