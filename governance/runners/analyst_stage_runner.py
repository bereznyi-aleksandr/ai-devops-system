#!/usr/bin/env python3
"""WRK-Cx ANALYST stage: build a governed task request and dispatch the configured LLM provider."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4

from bem931_runner_lib import (
    ARTIFACTS,
    CHANNELS,
    ROOT,
    append_jsonl,
    first_pending,
    now_iso,
    write_result,
)

CONTOURS = ["WRK-C1", "WRK-C2", "WRK-C3"]
PROVIDER_CONFIG = ROOT / "governance/config/provider_config.json"


def channel_name(contour_id: str, suffix: str) -> Path:
    prefix = contour_id.lower().replace("-", "_")
    return CHANNELS / f"{prefix}_to_{suffix}.jsonl"


def find_task() -> tuple[str | None, dict[str, Any] | None]:
    for contour in CONTOURS:
        task = first_pending(channel_name(contour, "analyst"))
        if task:
            return contour, task
    return None, None


def task_terms(objective: str) -> list[str]:
    words = re.findall(r"[A-Za-zА-Яа-я0-9_]+", objective.lower())
    ignored = {"with", "from", "that", "this", "для", "через", "после", "задача"}
    return sorted({word for word in words if len(word) >= 5 and word not in ignored})[:12]


def build_analysis_request(contour_id: str, task: dict[str, Any]) -> dict[str, Any]:
    objective = str(task.get("task") or task.get("objective") or "").strip()
    if not objective:
        raise ValueError("analysis objective is empty")
    trace_id = str(task.get("trace_id") or f"analysis_{uuid4().hex[:12]}")
    terms = task_terms(objective)
    return {
        "trace_id": trace_id,
        "role": f"{contour_id}.ANALYST",
        "contour_id": contour_id,
        "objective": objective,
        "task_terms": terms,
        "constraints": task.get("constraints") or [],
        "required_output": {
            "format": "json",
            "fields": [
                "objective",
                "assumptions",
                "steps",
                "acceptance",
                "risks",
            ],
            "rules": [
                "steps must be specific to the objective and executable",
                "acceptance must be independently verifiable",
                "do not assume success or skip validation",
            ],
        },
        "created_at": now_iso(),
    }


def build_claude_task(request: dict[str, Any]) -> str:
    return (
        "Create a task-specific implementation plan as strict JSON. "
        "Do not use generic fixed steps. The JSON must contain objective, "
        "assumptions, steps, acceptance, and risks. "
        f"Governed request:\n{json.dumps(request, ensure_ascii=False, indent=2)}"
    )


def configured_provider() -> tuple[str, dict[str, Any]]:
    config = json.loads(PROVIDER_CONFIG.read_text(encoding="utf-8"))
    provider_id = str(config["roles"]["analyst"]["primary"])
    provider = config["providers"][provider_id]
    if not provider.get("enabled"):
        raise RuntimeError(f"primary analyst provider disabled: {provider_id}")
    return provider_id, provider


def dispatch_provider(request: dict[str, Any]) -> dict[str, Any]:
    provider_id, provider = configured_provider()
    workflow_id = str(provider["workflow_id"])
    if os.environ.get("BEM934_OFFLINE_SMOKE") == "1":
        return {
            "status": "SMOKE_ONLY",
            "provider": provider_id,
            "workflow_id": workflow_id,
        }

    token = (
        os.environ.get("AI_SYSTEM_GITHUB_PAT")
        or os.environ.get("GH_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
    )
    repository = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repository:
        raise RuntimeError("GitHub dispatch token/repository unavailable")

    payload = {
        "ref": os.environ.get("GITHUB_REF_NAME") or "main",
        "inputs": {
            "role": "analyst",
            "provider": provider_id,
            "trace_id": request["trace_id"],
            "cycle_id": str(request.get("cycle_id") or ""),
            "task_type": "contour_analysis",
            "task": build_claude_task(request),
        },
    }
    url = (
        f"https://api.github.com/repos/{repository}/actions/workflows/"
        f"{workflow_id}/dispatches"
    )
    api_request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "bem934-analyst-stage",
        },
        method="POST",
    )
    with urllib.request.urlopen(api_request, timeout=30) as response:
        status = response.status
    if status != 204:
        raise RuntimeError(f"provider dispatch returned HTTP {status}")
    return {
        "status": "DISPATCHED",
        "provider": provider_id,
        "workflow_id": workflow_id,
        "http_status": status,
    }


def smoke() -> dict[str, Any]:
    task = {
        "trace_id": "bem934_wrk_c1_stage_smoke",
        "task": (
            "Implement an idempotent retry policy for payment webhook delivery "
            "and verify duplicate suppression."
        ),
        "constraints": ["preserve existing receipts", "fail closed"],
    }
    request = build_analysis_request("WRK-C1", task)
    prompt = build_claude_task(request)
    forbidden = [
        "verify objective",
        "prepare execution boundary",
        "request auditor pre-check",
    ]
    checks = {
        "objective_preserved": request["objective"] == task["task"],
        "task_terms_specific": {"retry", "payment", "webhook", "duplicate"}.intersection(
            request["task_terms"]
        )
        != set(),
        "strict_json_plan_requested": "strict JSON" in prompt,
        "historical_fixed_plan_absent": not any(item in prompt for item in forbidden),
        "provider_is_claude": configured_provider()[1]["workflow_id"] == "claude.yml",
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "request": request,
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

    contour_id, task = find_task()
    if not task or not contour_id:
        write_result(
            "analyst_no_task",
            {"role": "WRK-Cx.ANALYST", "result": "no_task"},
        )
        return "no_task"

    request = build_analysis_request(contour_id, task)
    request["cycle_id"] = task.get("cycle_id") or ""
    plan_dir = ARTIFACTS / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    request_path = plan_dir / f"{request['trace_id']}_analysis_request.json"
    request_path.write_text(
        json.dumps(request, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    dispatch = dispatch_provider(request)
    expected_plan = (
        f"governance/reports/{request['trace_id']}.md"
    )
    routed = {
        "trace_id": request["trace_id"],
        "status": "provider_dispatched",
        "from": request["role"],
        "to": f"{contour_id}.AUDITOR",
        "contour_id": contour_id,
        "phase": "pre_check_pending_provider_result",
        "analysis_request_path": str(request_path.relative_to(ROOT)),
        "expected_plan_path": expected_plan,
        "provider_dispatch": dispatch,
        "task": request["objective"],
        "created_at": now_iso(),
    }
    append_jsonl(channel_name(contour_id, "auditor_pre"), routed)
    write_result(
        "analyst_provider_dispatch",
        {**routed, "status": "completed"},
    )
    return f"{contour_id}_analysis_dispatched_to_{dispatch['provider']}"


if __name__ == "__main__":
    print(f"RUNNER: {main()}")
    sys.exit(0)
