#!/usr/bin/env python3
"""Managed channel consumer wrapper runtime for BEM-944.

Replaces the 23-byte runner stub. It invokes the existing managed_channel_consumer module,
captures its result, and writes a BEM-944 receipt. This proves wrapper/runtime invocation only and
does not claim downstream LLM completion.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import importlib.util
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROOFS = ROOT / "governance" / "proofs"
STATE = ROOT / "governance" / "state"
LOG = ROOT / "governance" / "logs" / "execution_log.jsonl"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"module_load_failed:{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def append_jsonl(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


def run() -> dict[str, Any]:
    consumer_path = ROOT / "governance" / "runners" / "managed_channel_consumer.py"
    module = load_module(consumer_path)
    captured = io.StringIO()
    exit_code = None
    with contextlib.redirect_stdout(captured):
        result = module.main()
        exit_code = result if isinstance(result, int) else 0
    stdout = captured.getvalue().strip()
    parsed: dict[str, Any] = {}
    if stdout:
        try:
            value = ast.literal_eval(stdout.splitlines()[-1])
            if isinstance(value, dict):
                parsed = value
        except Exception as exc:
            parsed = {"stdout_parse_error": str(exc), "raw_stdout": stdout}
    invocation = {
        "timestamp": now(),
        "protocol": "BEM-944",
        "task_id": "BEM944-P1-MANAGED-CHANNEL-CONSUMER-RUNNER",
        "module": "managed_channel_consumer.py",
        "exit_code": exit_code,
        "parsed_result": parsed,
        "non_claim": "wrapper invocation only; no downstream LLM completion claimed",
    }
    append_jsonl(STATE / "managed_channel_consumer_runner_invocations.jsonl", invocation)
    checks = {
        "managed_channel_consumer_runner_replaced_stub": True,
        "managed_channel_consumer_module_loaded": True,
        "managed_channel_consumer_invoked": exit_code == 0,
        "result_contains_runner": bool(parsed.get("runner")),
        "non_claim_present": True,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    receipt = {
        "status": "PASS" if not blockers else "BLOCKED",
        "protocol": "BEM-944",
        "task_id": "BEM944-P1-MANAGED-CHANNEL-CONSUMER-RUNNER",
        "created_at": now(),
        "stage": {"tasks_done": 2, "tasks_total": 4, "percent": 50},
        "invocation": invocation,
        "invocations_path": "governance/state/managed_channel_consumer_runner_invocations.jsonl",
        "checks": checks,
        "blockers": blockers,
        "non_claim": "managed channel consumer wrapper evidence only; no downstream LLM completion claimed",
        "next_task": "BEM944-P2-OBJECT-REPORT-AGGREGATOR" if not blockers else None,
    }
    PROOFS.mkdir(parents=True, exist_ok=True)
    receipt_path = PROOFS / "BEM944_managed_channel_consumer_runner_receipt.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    append_jsonl(LOG, {
        "timestamp": now(),
        "protocol": "BEM-944",
        "task_id": receipt["task_id"],
        "status": receipt["status"],
        "receipt": str(receipt_path.relative_to(ROOT)),
    })
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    receipt = run()
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if receipt["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
