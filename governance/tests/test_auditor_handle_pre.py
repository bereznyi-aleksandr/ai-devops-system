#!/usr/bin/env python3
"""Regression test for the real WRK-C1 AUDITOR.pre channel path."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

RUNNERS = Path(__file__).resolve().parents[1] / "runners"
if str(RUNNERS) not in sys.path:
    sys.path.insert(0, str(RUNNERS))

import auditor_stage_runner as runner  # noqa: E402


def write_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="bem934-auditor-pre-") as tmp:
        root = Path(tmp)
        channels = root / "governance" / "channels"
        results: list[tuple[str, dict]] = []

        runner.ROOT = root
        runner.CHANNELS = channels
        runner.CURATOR_FEEDBACK = channels / "wrk_to_curator_feedback.jsonl"
        runner.write_result = lambda name, payload: results.append((name, dict(payload)))

        plan_rel = "governance/proofs/auditor_pre_fixture_plan.json"
        plan_path = root / plan_rel
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan = {
            "objective": (
                "Implement idempotent payment webhook retry and duplicate suppression "
                "with durable delivery receipts."
            ),
            "assumptions": ["The receipt store is durable."],
            "steps": [
                "Derive an idempotency key from the payment webhook event id.",
                "Persist each retry attempt and enforce bounded exponential backoff.",
                "Replay duplicate webhook events and verify one outbound delivery.",
            ],
            "acceptance": [
                "A replay test passes for duplicate payment webhook events.",
                "The receipt records one successful delivery for each event id.",
            ],
            "risks": ["Concurrent delivery races."],
        }
        plan_path.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        task = {
            "trace_id": "bem934_auditor_handle_pre_regression",
            "status": "pending",
            "task": (
                "Implement idempotent payment webhook retry and duplicate suppression "
                "with durable delivery receipts."
            ),
            "task_terms": [
                "idempotent",
                "payment",
                "webhook",
                "retry",
                "duplicate",
                "receipt",
            ],
            "expected_plan_path": plan_rel,
        }
        pre_channel = channels / "wrk_c1_to_auditor_pre.jsonl"
        write_jsonl(pre_channel, task)

        original_argv = sys.argv[:]
        try:
            sys.argv = ["auditor_stage_runner.py"]
            result = runner.main()
        finally:
            sys.argv = original_argv

        executor_channel = channels / "wrk_c1_to_executor.jsonl"
        executor_rows = [
            json.loads(line)
            for line in executor_channel.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        checks = {
            "main_consumed_real_pre_channel": result == "WRK-C1_pre_check_pass",
            "executor_channel_written": bool(executor_rows),
            "executor_route_selected": (
                bool(executor_rows)
                and executor_rows[-1].get("to") == "WRK-C1.EXECUTOR"
            ),
            "semantic_pre_check_pass": (
                bool(executor_rows)
                and executor_rows[-1].get("pre_check") == "PASS"
            ),
            "result_artifact_emitted": (
                bool(results) and results[-1][0] == "auditor_pre_check"
            ),
        }
        payload = {
            "status": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "result": result,
            "executor_row": executor_rows[-1] if executor_rows else None,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
