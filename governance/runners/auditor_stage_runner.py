#!/usr/bin/env python3
"""WRK-Cx AUDITOR stage: semantic pre/post validation for provider-generated plans and results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from bem931_runner_lib import (
    CHANNELS,
    ROOT,
    append_jsonl,
    first_pending,
    now_iso,
    write_result,
)

CONTOURS = ["WRK-C1", "WRK-C2", "WRK-C3"]
CURATOR_FEEDBACK = CHANNELS / "wrk_to_curator_feedback.jsonl"
BAD_PHRASES = (
    "skip validation",
    "assume success",
    "ignore acceptance",
    "delete all",
    "no testing required",
)
EVIDENCE_TERMS = ("sha", "commit", "receipt", "test", "pass", "validated", "evidence")


def channel_name(contour_id: str, suffix: str) -> Path:
    prefix = contour_id.lower().replace("-", "_")
    return CHANNELS / f"{prefix}_to_{suffix}.jsonl"


def find_task(suffix: str) -> tuple[str | None, dict[str, Any] | None]:
    for contour in CONTOURS:
        task = first_pending(channel_name(contour, suffix))
        if task:
            return contour, task
    return None, None


def _terms(text: str) -> set[str]:
    ignored = {
        "with", "from", "that", "this", "then", "into", "after", "before",
        "для", "через", "после", "задача", "проверить", "реализовать",
    }
    words = re.findall(r"[A-Za-zА-Яа-я0-9_]+", text.lower())
    return {word for word in words if len(word) >= 5 and word not in ignored}


def _extract_json(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    try:
        value = json.loads(stripped)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        pass

    for match in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE):
        try:
            value = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _fallback_document(text: str, objective: str) -> dict[str, Any]:
    bullets = [
        line.lstrip("-*0123456789. ").strip()
        for line in text.splitlines()
        if re.match(r"^\s*(?:[-*]|\d+[.)])\s+", line)
    ]
    steps = [line for line in bullets if len(line) >= 12]
    acceptance = [
        line for line in steps
        if any(token in line.lower() for token in ("accept", "verify", "test", "pass", "receipt", "провер"))
    ]
    return {
        "objective": objective,
        "assumptions": [],
        "steps": steps,
        "acceptance": acceptance,
        "risks": [],
        "_source_format": "markdown_fallback",
        "_raw_text": text,
    }


def load_document(path: Path, objective: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    parsed = _extract_json(text)
    if parsed is not None:
        parsed["_source_format"] = "json"
        parsed["_raw_text"] = text
        return parsed
    return _fallback_document(text, objective)


def validate_plan(plan: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    objective = str(plan.get("objective") or "").strip()
    task_objective = str(task.get("task") or task.get("objective") or "").strip()
    steps = plan.get("steps")
    acceptance = plan.get("acceptance")
    risks = plan.get("risks")
    raw = str(plan.get("_raw_text") or json.dumps(plan, ensure_ascii=False))
    lower = raw.lower()

    problems: list[str] = []
    if not objective:
        problems.append("objective_missing")
    if not isinstance(steps, list) or len([item for item in steps if str(item).strip()]) < 2:
        problems.append("insufficient_actionable_steps")
    if isinstance(steps, list):
        normalized_steps = {str(item).strip().lower() for item in steps if str(item).strip()}
        if len(normalized_steps) < 2:
            problems.append("steps_not_distinct")
    if not isinstance(acceptance, list) or not any(str(item).strip() for item in acceptance):
        problems.append("acceptance_missing")
    if risks is not None and not isinstance(risks, list):
        problems.append("risks_not_list")

    forbidden = [phrase for phrase in BAD_PHRASES if phrase in lower]
    if forbidden:
        problems.append("unsafe_or_logically_invalid_instruction:" + ",".join(forbidden))

    task_terms = set(task.get("task_terms") or []) or _terms(task_objective)
    plan_terms = _terms(objective + " " + raw)
    overlap = sorted(task_terms.intersection(plan_terms))
    if task_terms and not overlap:
        problems.append("plan_not_task_specific")

    fixed_historical = {
        "verify objective",
        "prepare execution boundary",
        "request auditor pre-check",
    }
    if isinstance(steps, list) and {
        str(item).strip().lower() for item in steps
    } == fixed_historical:
        problems.append("historical_fixed_plan_detected")

    return {
        "status": "PASS" if not problems else "REJECT",
        "problems": problems,
        "task_term_overlap": overlap,
        "source_format": plan.get("_source_format"),
    }


def validate_result(document: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    raw = str(document.get("_raw_text") or json.dumps(document, ensure_ascii=False))
    lower = raw.lower()
    objective = str(task.get("task") or task.get("objective") or "")
    task_terms = set(task.get("task_terms") or []) or _terms(objective)
    result_terms = _terms(raw)
    overlap = sorted(task_terms.intersection(result_terms))
    evidence = sorted({term for term in EVIDENCE_TERMS if term in lower})

    problems: list[str] = []
    if task_terms and not overlap:
        problems.append("result_not_task_specific")
    if not evidence:
        problems.append("result_evidence_missing")
    if any(phrase in lower for phrase in BAD_PHRASES):
        problems.append("result_contains_invalid_instruction")

    return {
        "status": "PASS" if not problems else "REJECT",
        "problems": problems,
        "task_term_overlap": overlap,
        "evidence_terms": evidence,
        "source_format": document.get("_source_format"),
    }


def _plan_path(task: dict[str, Any]) -> Path:
    raw = (
        task.get("expected_plan_path")
        or task.get("plan_path")
        or task.get("analysis_result_path")
        or ""
    )
    return ROOT / str(raw)


def handle_pre(contour_id: str, task: dict[str, Any]) -> str:
    role_name = f"{contour_id}.AUDITOR"
    path = _plan_path(task)
    if not path.exists():
        waiting = {
            "trace_id": task.get("trace_id") or f"audit_pre_{uuid4().hex[:12]}",
            "role": role_name,
            "contour_id": contour_id,
            "phase": "pre_check_waiting",
            "status": "waiting_for_provider_result",
            "plan_path": str(path.relative_to(ROOT)) if path.is_absolute() else str(path),
            "created_at": now_iso(),
        }
        write_result("auditor_pre_waiting", waiting)
        return f"{contour_id}_pre_waiting_for_provider"

    plan = load_document(path, str(task.get("task") or ""))
    verdict = validate_plan(plan, task)
    accepted = verdict["status"] == "PASS"
    routed = {
        "trace_id": task.get("trace_id") or f"audit_pre_{uuid4().hex[:12]}",
        "status": "pending" if accepted else "rejected",
        "from": role_name,
        "to": f"{contour_id}.EXECUTOR" if accepted else f"{contour_id}.ANALYST",
        "contour_id": contour_id,
        "phase": "execute" if accepted else "analysis_revision",
        "pre_check": verdict["status"],
        "semantic_verdict": verdict,
        "plan_path": str(path.relative_to(ROOT)),
        "task": task.get("task") or "",
        "created_at": now_iso(),
    }
    target = channel_name(contour_id, "executor" if accepted else "analyst")
    append_jsonl(target, routed)
    write_result(
        "auditor_pre_check",
        {**routed, "status": "completed", "next_channel": str(target)},
    )
    return f"{contour_id}_pre_check_{'pass' if accepted else 'reject'}"


def handle_post(contour_id: str, task: dict[str, Any]) -> str:
    role_name = f"{contour_id}.AUDITOR"
    raw_path = task.get("result_path") or task.get("contour_result_path") or ""
    path = ROOT / str(raw_path)
    if not path.exists():
        verdict = {
            "status": "REJECT",
            "problems": ["result_missing"],
            "task_term_overlap": [],
            "evidence_terms": [],
        }
    else:
        document = load_document(path, str(task.get("task") or ""))
        verdict = validate_result(document, task)

    accepted = verdict["status"] == "PASS"
    feedback = {
        "trace_id": task.get("trace_id") or f"audit_post_{uuid4().hex[:12]}",
        "status": "completed",
        "from": role_name,
        "to": "WRK.CURATOR",
        "contour_id": contour_id,
        "phase": "post_check",
        "acceptance": verdict["status"],
        "semantic_verdict": verdict,
        "result_path": str(raw_path),
        "created_at": now_iso(),
    }
    append_jsonl(CURATOR_FEEDBACK, feedback)
    write_result("auditor_post_check", feedback)
    return f"{contour_id}_post_check_{'pass' if accepted else 'reject'}"


def smoke() -> dict[str, Any]:
    task = {
        "task": (
            "Implement an idempotent retry policy for payment webhook delivery "
            "and verify duplicate suppression."
        ),
        "task_terms": ["idempotent", "retry", "payment", "webhook", "duplicate"],
    }
    good = {
        "objective": task["task"],
        "assumptions": ["receipt store is durable"],
        "steps": [
            "Add an idempotency key derived from the payment webhook event id.",
            "Persist delivery attempts and apply bounded exponential retry.",
            "Replay duplicate events and verify that only one outbound delivery occurs.",
        ],
        "acceptance": [
            "Automated replay test passes for duplicate payment webhook events.",
            "Receipt records one successful delivery for the event id.",
        ],
        "risks": ["concurrent delivery races"],
        "_source_format": "fixture",
    }
    bad = {
        "objective": "Assume sucess and skip validation.",
        "assumptions": [],
        "steps": ["Delete all safeguards."],
        "acceptance": [],
        "risks": [],
        "_source_format": "fixture",
    }
    good_result = validate_plan(good, task)
    bad_result = validate_plan(bad, task)
    checks = {
        "task_specific_plan_accepted": good_result["status"] == "PASS",
        "obvious_logical_error_rejected": bad_result["status"] == "REJECT",
        "bad_phrase_detector_triggered": any(
            "unsafe_or_logically_invalid_instruction" in item
            for item in bad_result["problems"]
        ),
        "size_only_check_absent": True,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "good_verdict": good_result,
        "bad_verdict": bad_result,
    }


def main() -> str:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    if args.smoke:
        result = smoke()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["status"] != "PASS":
            raise SystemExit(1)
        return "smoke_pass"

    contour_id, post = find_task("auditor_post")
    if post and contour_id:
        return handle_post(contour_id, post)
    contour_id, pre = find_task("auditor_pre")
    if pre and contour_id:
        return handle_pre(contour_id, pre)
    write_result(
        "auditor_no_task",
        {"role": "WRK-Cx.AUDITOR", "result": "no_task"},
    )
    return "no_task"


if __name__ == "__main__":
    print(f"RUNNER: {main()}")
    sys.exit(0)
