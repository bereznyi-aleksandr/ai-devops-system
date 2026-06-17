#!/usr/bin/env python3
"""BEM-934 request-driven actions executed by the indexed GitHub-hosted state workflow."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REQUEST = ROOT / "governance/runtime/bem934_state_request.json"
PROOFS = ROOT / "governance/proofs"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_receipt(name: str, payload: dict[str, Any]) -> Path:
    PROOFS.mkdir(parents=True, exist_ok=True)
    path = PROOFS / name
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def verify_deprecated_selfhosted() -> None:
    marker = (
        "# DEPRECATED: requires self-hosted runner, operator will never "
        "provide one. See BEM-934."
    )
    targets = [
        ROOT / ".github/workflows/codex-local.yml",
        ROOT / ".github/workflows/codex-local-assembled.yml",
    ]
    checks = {
        str(path.relative_to(ROOT)): path.exists()
        and path.read_text(encoding="utf-8").startswith(marker)
        for path in targets
    }
    status = "PASS" if all(checks.values()) else "BLOCKED"
    write_receipt(
        "BEM934_deprecate_selfhosted_receipt.json",
        {
            "status": status,
            "protocol": "BEM-934",
            "task_id": "BEM934-DEPRECATE-SELFHOSTED",
            "created_at": utc_now(),
            "checks": checks,
            "active_target_policy": "FORBID_NEW_REFERENCES_TO_CODEX_LOCAL",
        },
    )
    if status != "PASS":
        raise SystemExit(1)


def verify_prompt_reconnect() -> None:
    workflow = ROOT / ".github/workflows/claude.yml"
    text = workflow.read_text(encoding="utf-8")
    checks = {
        "bridge_step_present": "BEM-934 prompt assembler bridge" in text,
        "assembler_cli_present": (
            "scripts/prompt_assembler.py --element-id" in text
        ),
        "assembled_prompt_injected": (
            "# BEM-934 GOVERNED ASSEMBLED ROLE PROMPT" in text
        ),
    }
    status = "PASS" if all(checks.values()) else "BLOCKED"
    write_receipt(
        "BEM934_prompt_assembler_reconnect_receipt.json",
        {
            "status": status,
            "protocol": "BEM-934",
            "task_id": "BEM934-PROMPT-ASSEMBLER-RECONNECT",
            "created_at": utc_now(),
            "workflow": ".github/workflows/claude.yml",
            "checks": checks,
            "missing": [key for key, value in checks.items() if not value],
        },
    )
    if status != "PASS":
        raise SystemExit(1)


def stage_runner_smoke() -> None:
    runners = ROOT / "governance/runners"
    if str(runners) not in sys.path:
        sys.path.insert(0, str(runners))

    import analyst_stage_runner
    import auditor_stage_runner

    analyst = analyst_stage_runner.smoke()
    auditor = auditor_stage_runner.smoke()
    analyst_source = (runners / "analyst_stage_runner.py").read_text(
        encoding="utf-8"
    )
    auditor_source = (runners / "auditor_stage_runner.py").read_text(
        encoding="utf-8"
    )
    checks = {
        "analyst_smoke_pass": analyst.get("status") == "PASS",
        "auditor_smoke_pass": auditor.get("status") == "PASS",
        "task_specific_request": bool(
            analyst.get("checks", {}).get("task_terms_specific")
        ),
        "configured_provider_is_claude": bool(
            analyst.get("checks", {}).get("provider_is_claude")
        ),
        "provider_workflow_dispatch_present": (
            "/actions/workflows/" in analyst_source
        ),
        "historical_fixed_plan_absent": bool(
            analyst.get("checks", {}).get("historical_fixed_plan_absent")
        ),
        "semantic_auditor_rejects_logical_error": bool(
            auditor.get("checks", {}).get(
                "obvious_logical_error_rejected"
            )
        ),
        "size_only_audit_absent": "st_size > 50" not in auditor_source,
    }
    status = "PASS" if all(checks.values()) else "BLOCKED"
    write_receipt(
        "BEM934_stage_runner_reconnect_receipt.json",
        {
            "status": status,
            "protocol": "BEM-934",
            "task_id": "BEM934-STAGE-RUNNER-RECONNECT",
            "created_at": utc_now(),
            "checks": checks,
            "analyst": analyst,
            "auditor": auditor,
            "artifacts": [
                "governance/runners/analyst_stage_runner.py",
                "governance/runners/auditor_stage_runner.py",
            ],
            "missing": [key for key, value in checks.items() if not value],
        },
    )
    if status != "PASS":
        raise SystemExit(1)


ACTIONS = {
    "deprecate_selfhosted": verify_deprecated_selfhosted,
    "reconnect_prompt_assembler": verify_prompt_reconnect,
    "stage_runner_smoke": stage_runner_smoke,
}


def main() -> int:
    request = json.loads(REQUEST.read_text(encoding="utf-8"))
    action = str(request.get("action") or "").strip()
    if not action:
        return 0
    handler = ACTIONS.get(action)
    if handler is None:
        raise SystemExit(f"unsupported BEM-934 action: {action}")
    handler()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
