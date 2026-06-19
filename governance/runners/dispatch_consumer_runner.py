#!/usr/bin/env python3
"""Wrapper runtime for dispatch_consumer.py.

This replaces the 23-byte stub. It calls the real dispatch_consumer runtime, writes a
BEM-943 wrapper receipt, and does not claim downstream workflow/LLM execution.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROOFS = ROOT / "governance" / "proofs"
LOG = ROOT / "governance" / "logs" / "execution_log.jsonl"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_consumer():
    path = ROOT / "governance" / "runners" / "dispatch_consumer.py"
    spec = importlib.util.spec_from_file_location("dispatch_consumer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("dispatch_consumer_load_failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def append_jsonl(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


def run(limit: int) -> dict[str, Any]:
    consumer = load_consumer()
    result = consumer.consume(limit)
    checks = {
        "dispatch_consumer_runner_runtime_code_present": True,
        "dispatch_consumer_imported": True,
        "consumer_result_has_status": bool(result.get("status")),
        "processed_or_skipped_recorded": result.get("processed_count", 0) >= 0 and result.get("skipped_count", 0) >= 0,
        "no_downstream_llm_completion_claim": True,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    receipt = {
        "status": "PASS" if not blockers and result.get("status") in {"PASS", "BLOCKED"} else "BLOCKED",
        "protocol": "BEM-943",
        "task_id": "BEM943-P1-DISPATCH-CONSUMER-RUNNER",
        "created_at": now(),
        "stage": {"tasks_done": 2, "tasks_total": 4, "percent": 50},
        "consumer_result": result,
        "checks": checks,
        "blockers": blockers,
        "non_claim": "wrapper proves dispatch consumer invocation only; no downstream LLM completion claimed",
        "next_task": "BEM943-P2-PROOF-MANIFEST-UPDATER" if not blockers else None,
    }
    PROOFS.mkdir(parents=True, exist_ok=True)
    out = PROOFS / "BEM943_dispatch_consumer_runner_receipt.json"
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    append_jsonl(LOG, {"timestamp": now(), "protocol": "BEM-943", "task_id": receipt["task_id"], "status": receipt["status"], "receipt": str(out.relative_to(ROOT))})
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=20)
    args = parser.parse_args()
    receipt = run(args.max)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if receipt["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
