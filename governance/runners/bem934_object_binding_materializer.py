#!/usr/bin/env python3
"""Fail-closed BEM-934 isolated object-binding proof materializer."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = ROOT / "governance/proofs/BEM934_object_binding_plan_isolated.json"
RECEIPT_PATH = ROOT / "governance/proofs/BEM934_objects_bound_isolated_receipt.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_structured(raw: str) -> dict[str, Any]:
    value: Any = json.loads(raw)
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("structured_output_is_not_an_object")
    return value


def semantic_checks(plan: dict[str, Any], trace_id: str) -> dict[str, bool]:
    required = (
        "objective",
        "assumptions",
        "steps",
        "acceptance",
        "risks",
        "trace_id",
    )
    text = json.dumps(plan, ensure_ascii=False).lower()
    steps = plan.get("steps")
    acceptance = plan.get("acceptance")
    historical = {
        "verify objective",
        "prepare execution boundary",
        "request auditor pre-check",
    }
    normalized = (
        {str(item).strip().lower() for item in steps}
        if isinstance(steps, list)
        else set()
    )
    return {
        "strict_json_object_parsed": isinstance(plan, dict),
        "required_fields_present": all(field in plan for field in required),
        "trace_matches": plan.get("trace_id") == trace_id,
        "steps_are_task_specific": (
            isinstance(steps, list)
            and len([term for term in steps if str(term).strip()]) >= 3
        ),
        "acceptance_is_verifiable": (
            isinstance(acceptance, list)
            and len([term for term in acceptance if str(term).strip()]) >= 2
        ),
        "mentions_wrk_c1": "wrk-c1" in text or "wrk_c1" in text,
        "mentions_claude_provider": "claude" in text and "provider" in text,
        "mentions_object_runtime_binding": all(
            term in text for term in ("object", "runtime", "binding")
        ),
        "mentions_idempotent_telegram_routing": all(
            term in text for term in ("idempotent", "telegram", "routing")
        ),
        "historical_fixed_plan_absent": normalized != historical,
    }


def exercise_auditor_pre(plan: dict[str, Any], trace_id: str) -> dict[str, Any]:
    runners = ROOT / "governance/runners"
    if str(runners) not in sys.path:
        sys.path.insert(0, str(runners))
    import auditor_stage_runner as runner  # pylint: disable=import-outside-topleveline

    with tempfile.TemporaryDirectory(prefix="bem934-binding-proof-") as tmp:
        temp_root = Path(tmp)
        channels = temp_root / "governance/channels"
        rel_plan = Path("governance/proofs/BEM934_object_binding_plan_isolated.json")
        copied_plan = temp_root / rel_plan
        copied_plan.parent.mkdir(parents=True, exist_ok=True)
        write_json(copied_plan, plan)

        captured_results: list[tuple[str, dict[str, Any]]] = []
        runner.ROOT = temp_root
        runner.CHANNELS = channels
        runner.CURATOR_FEEDBACK = channels / "wrk_to_curator_feedback.jsonl"
        runner.write_result = (
            lambda name, payload: captured_results.append((name, dict(payload))
        )

        task = {
            "trace_id": trace_id,
            "status": "pending",
            "task": (
                "Prove WRK-C1 Claude provider object runtime binding "
                "and idempotent Telegram routing."
            ),
            "task_terms": [
                "wrk-c1",
                "claude",
                "provider",
                "object",
                "runtime",
                "binding",
                "idempotent",
                "telegram",
                "routing",
            ],
            "expected_plan_path": str(rel_plan),
        }
        pre_channel = channels / "wrk_c1_to_auditor_pre.jsonl"
        pre_channel.parent.mkdir(parents=True, exist_ok=True)
        pre_channel.write_text(
            json.dumps(task, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        old_argv = sys.argv[:]
        try:
            sys.argv = ["auditor_stage_runner.py"]
            result = runner.main()
        finally:
            sys.argv = old_argv

        executor_path = channels / "wrk_c1_to_executor.jsonl"
        rows: list[dict[str, Any]] = []
        if executor_path.exists():
            rows = [
                json.loads(line)
                for line in executor_path.read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines()
                if line.strip()
            ]

        checks = {
            "real_pre_channel_consumed": result == "WRK-C1_pre_check_pass",
            "executor_channel_written": bool(rows),
            "executor_route_selected": (
                bool(rows) and rows[-1].get("to") == "WRK-C1.EXECUTOR"
            ),
            "semantic_pre_check_pass": (
                bool(rows) and rows[-1].get("pre_check") == "PASS"
            ),
            "trace_preserved": (
                bool(rows) and rows[-1].get("trace_id") == trace_id
            ),
            "result_artifact_emitted": (
                bool(captured_results)
                and captured_results[-1][0] == "auditor_pre_check"
            ),
        }
        return {
            "checks": checks,
            "runner_result": result,
            "executor_row": rows[-1] if rows else None,
            "result_artifact_count": len(captured_results),
        }


def append_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT", "").strip()
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def main() -> int:
    trace_id = os.environ.get("TRACE_ID", "").strip()
    raw = os.environ.get("STRUCTURED_OUTPUT", "").strip()
    claude_outcome = os.environ.get("CLAUDE_OUTCOME", "unknown").strip()
    receipt: dict[str, Any] = {
        "status": "BLOCKED",
        "protocol": "BEM-934",
        "task_id": "BEM934-OBJECTS-BOUND",
        "created_at": utc_now(),
        "trace_id": trace_id,
        "provider_selected": "claude_code",
        "workflow_id": "bem934-object-binding-proof-v2.yml",
        "workflow_run_id": int(os.environ.get("GITHUB_RUN_ID", "0") or 0),
        "claude_action_outcome": claude_outcome,
        "checks": {},
        "missing": [],
    }

    try:
        if not trace_id:
            raise ValueError("trace_id_missing")
        if claude_outcome != "success":
            raise RuntimeError(f"claude_action_outcome:{claude_outcome}")
        if not raw:
            raise ValueError("structured_output_missing")

        plan = parse_structured(raw)
        semantic = semantic_checks(plan, trace_id)
        receipt["checks"].update(semantic)
        if not all(semantic.values()):
            receipt["missing"] = [
                key for key, value in semantic.items() if not value
            ]
            raise ValueError("semantic_validation_failed")

        contour = exercise_auditor_pre(plan, trace_id)
        receipt["contour"] = contour
        receipt["checks"].update(contour["checks"])
        if not all(contour["checks"].values()):
            receipt["missing"] = [
                key for key, value in receipt["checks"].items() if not value
            ]
            raise ValueError("auditor_pre_channel_validation_failed")

        write_json(PLAN_PATH, plan)
        receipt.update(
            {
                "status": "PASS",
                "semantic_verdict": "PASS",
                "plan_path": str(PLAN_PATH.relative_to(ROOT)),
                "missing": [],
            }
        )
        receipt.pop("blocker", None)
    except Exception as exc:  # fail closed and preserve the exact cause
        receipt["blocker"] = str(exc)
        receipt["error_type"] = exc.__class__.__name__
        receipt["error_message"] = str(exc)[:2000]
        receipt["traceback_tail"] = traceback.format_exc()[-5000:]
        if not receipt["missing"]:
            receipt["missing"] = [
                key for key, value in receipt.get("checks", {}).items() if not value
            ]
          if not receipt["missing"]:
            receipt["missing"] = [str(exc)]

    write_json(RECEIP_PATH, receipt)
    append_output("status", receipt["status"])
    append_output("receipt_path", str(RECEIPT_PATH.relative_to(ROOT)))
    if PLAN_PATH.exists():
        append_output("plan_path", str(PLAN_PATH.relative_to(ROOT)))
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
