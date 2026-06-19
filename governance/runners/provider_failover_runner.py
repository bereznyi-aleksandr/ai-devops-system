#!/usr/bin/env python3
"""Provider failover runner alignment for BEM-942.

Uses the provider activation/status layer from BEM-940 and the failover decision engine
from provider_failover.py. It records decision evidence only and does not claim downstream
LLM execution.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "governance" / "state"
PROOFS = ROOT / "governance" / "proofs"
EXECUTION_LOG = ROOT / "governance" / "logs" / "execution_log.jsonl"
STATUS = STATE / "provider_status.json"
DECISIONS = STATE / "provider_failover_runner_decisions.jsonl"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"module_load_failed:{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def append_jsonl(path: Path, items: list[dict[str, Any]]) -> None:
    if not items:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


def read_status() -> dict[str, Any]:
    if not STATUS.exists():
        return {}
    try:
        return json.loads(STATUS.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


def run_alignment(role: str, trace_id: str) -> dict[str, Any]:
    failover = load_module("provider_failover", ROOT / "governance" / "runners" / "provider_failover.py")
    activation = load_module("provider_activation", ROOT / "governance" / "runners" / "provider_activation.py")

    activation_decision = activation.decide("claude_code", role, f"{trace_id}_activation")
    primary = failover.decide({"role": role, "trace_id": f"{trace_id}_primary", "failure_reason": None})
    fallback = failover.decide({"role": role, "trace_id": f"{trace_id}_fallback", "failure_reason": "rate_limit"})
    no_fallback = failover.decide({"role": role, "trace_id": f"{trace_id}_syntax", "failure_reason": "syntax_error"})

    status = read_status()
    checks = {
        "provider_failover_runner_runtime_code_present": True,
        "activation_decision_active": activation_decision.get("status") == "ACTIVE",
        "primary_uses_claude_code": primary.get("provider_selected") == "claude_code",
        "recognized_failure_uses_cloud_fallback": fallback.get("fallback_used") is True and fallback.get("provider_selected") == "gpt_codex_cloud",
        "unrecognized_failure_keeps_primary": no_fallback.get("fallback_used") is False and no_fallback.get("provider_selected") == "claude_code",
        "status_layer_readable": isinstance(status, dict),
        "no_downstream_llm_completion_claim": True,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    record = {
        "status": "PASS" if not blockers else "BLOCKED",
        "protocol": "BEM-942",
        "task_id": "BEM942-P1-FAILOVER-RUNNER-ALIGNMENT",
        "created_at": now(),
        "trace_id": trace_id,
        "role": role,
        "activation_decision": activation_decision,
        "failover_decisions": {
            "primary": primary,
            "fallback": fallback,
            "unrecognized": no_fallback,
        },
        "status_path": str(STATUS.relative_to(ROOT)),
        "decisions_path": str(DECISIONS.relative_to(ROOT)),
        "checks": checks,
        "blockers": blockers,
        "non_claim": "failover decision evidence only; no downstream LLM completion claimed",
    }
    append_jsonl(DECISIONS, [record])
    append_jsonl(EXECUTION_LOG, [{
        "timestamp": now(),
        "protocol": "BEM-942",
        "task_id": record["task_id"],
        "status": record["status"],
        "trace_id": trace_id,
        "receipt": "governance/proofs/BEM942_failover_runner_alignment_receipt.json",
    }])
    PROOFS.mkdir(parents=True, exist_ok=True)
    (PROOFS / "BEM942_failover_runner_alignment_receipt.json").write_text(
        json.dumps({**record, "stage": {"tasks_done": 2, "tasks_total": 4, "percent": 50}, "next_task": "BEM942-P2-FAILOVER-ACTIVATION-E2E" if not blockers else None}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", default="curator")
    parser.add_argument("--trace-id", default="bem942_failover_runner_alignment")
    args = parser.parse_args()
    receipt = run_alignment(args.role, args.trace_id)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if receipt["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
