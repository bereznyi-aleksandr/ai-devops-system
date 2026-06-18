#!/usr/bin/env python3
"""Prepare BEM-934 closure without promoting release."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(".")
QUEUE = ROOT / "governance/roadmap/ACTIVE_QUEUE.json"
LIVE = ROOT / "governance/proofs/BEM934_live_test_receipt.json"
SUPERSEDED = ROOT / "governance/proofs/BEM934_live_test_receipt_superseded_replay.json"
PROVIDER = ROOT / "governance/config/provider_config.json"
PROTOCOL = ROOT / "governance/protocols/BEM934_Protocol.md"
AGENT_CONTEXT = ROOT / "governance/AGENT_CONTEXT.md"
SYSTEM_STATUS = ROOT / "SYSTEM_STATUS.md"
CLAUDE_WORKFLOW = ROOT / ".github/workflows/claude.yml"
RECEIPT = ROOT / "governance/proofs/BEM934_close_preparation_receipt.json"
EXECUTION_LOG = ROOT / "governance/logs/execution_log.jsonl"

TARGET_INPUTS = ("role", "provider", "trace_id", "cycle_id", "task_type", "task")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonicalize_dispatch_inputs(text: str) -> str:
    """Remove defaults and require canonical workflow_dispatch inputs."""
    lines = text.splitlines()
    output: list[str] = []
    in_inputs = False
    current: str | None = None

    for line in lines:
        if line == "    inputs:":
            in_inputs = True
            current = None
            output.append(line)
            continue

        if in_inputs:
            if line.startswith("      ") and not line.startswith("        ") and line.rstrip().endswith(":"):
                current = line.strip()[:-1]
                output.append(line)
                continue

            if line.startswith("  ") and not line.startswith("    "):
                in_inputs = False
                current = None
            elif current in TARGET_INPUTS:
                stripped = line.strip()
                if stripped.startswith("default:"):
                    continue
                if stripped.startswith("required:"):
                    output.append("        required: true")
                    continue

        output.append(line)

    result = "\n".join(output) + "\n"

    # Verify every canonical input is present, required, and default-free.
    for name in TARGET_INPUTS:
        marker = f"      {name}:"
        start = result.find(marker)
        if start < 0:
            raise RuntimeError(f"claude_input_missing:{name}")
        candidates = [
            p
            for other in TARGET_INPUTS
            if (p := result.find(f"      {other}:", start + len(marker))) >= 0
        ]
        candidates += [
            p for p in (
                result.find("\n  issue_comment:", start),
                result.find("\n  issues:", start),
                result.find("\n  pull_request", start),
            ) if p >= 0
        ]
        end = min(candidates) if candidates else len(result)
        block = result[start:end]
        if "required: true" not in block:
            raise RuntimeError(f"claude_input_not_required:{name}")
        if "default:" in block:
            raise RuntimeError(f"claude_input_default_present:{name}")

    return result


def main() -> None:
    queue = load_json(QUEUE)
    live = load_json(LIVE)
    superseded = load_json(SUPERSEDED)
    provider = load_json(PROVIDER)

    telegram = live.get("telegram") if isinstance(live.get("telegram"), dict) else {}
    transport = live.get("transport") if isinstance(live.get("transport"), dict) else {}
    semantic = transport.get("semantic_result") if isinstance(transport.get("semantic_result"), dict) else {}
    live_checks = live.get("checks") if isinstance(live.get("checks"), dict) else {}
    providers = provider.get("providers") if isinstance(provider.get("providers"), dict) else {}
    roles = provider.get("roles") if isinstance(provider.get("roles"), dict) else {}
    claude = providers.get("claude_code") if isinstance(providers.get("claude_code"), dict) else {}
    self_hosted = providers.get("gpt_codex") if isinstance(providers.get("gpt_codex"), dict) else {}
    cloud = providers.get("gpt_codex_cloud") if isinstance(providers.get("gpt_codex_cloud"), dict) else {}

    checks = {
        "queue_current_close": queue.get("current_task") == "BEM934-CLOSE",
        "queue_nine_of_ten": queue.get("completed_summary", {}).get("tasks_done") == 9,
        "release_not_promoted": queue.get("release_status") == "FOLLOW_UP_REQUIRED",
        "live_receipt_v2_pass": live.get("status") == "PASS" and live.get("receipt_version") == 2,
        "live_operator_authored": telegram.get("operator_authored") is True,
        "live_not_bot_replay": telegram.get("automatic_bot_replay") is False,
        "live_release_not_promoted": live.get("release_promoted") is False,
        "live_semantic_executor_completed": (
            semantic.get("status") == "completed"
            and semantic.get("provider") == "claude"
            and semantic.get("role") == "executor"
            and semantic.get("blocker") is None
        ),
        "live_failed_history_disclosed": transport.get("historical_failed_attempt_count", 0) >= 1,
        "live_nested_checks_true": bool(live_checks) and all(v is True for v in live_checks.values()),
        "superseded_replay_archived": superseded.get("_superseded", {}).get("replacement_trace_id") == live.get("trace_id"),
        "claude_primary_all_roles": (
            claude.get("enabled") is True
            and claude.get("workflow_id") == "claude.yml"
            and all(
                isinstance(roles.get(role), dict)
                and roles[role].get("primary") == "claude_code"
                for role in ("curator", "analyst", "auditor", "executor")
            )
        ),
        "self_hosted_disabled_deprecated": self_hosted.get("enabled") is False and self_hosted.get("deprecated") is True,
        "cloud_reserve_not_self_hosted": cloud.get("requires_self_hosted") is False,
        "cloud_reserve_mechanical_disclosure": (
            cloud.get("execution_mode") == "optional_openai_responses_api_or_mechanical_fallback"
            and "OPENAI_API_KEY" in str(cloud.get("note", ""))
        ),
        "protocol_requires_external_auditor": "External auditor verdict is `APPROVED`" in PROTOCOL.read_text(encoding="utf-8"),
    }

    failed = [name for name, value in checks.items() if not value]
    if failed:
        raise RuntimeError("close_preparation_failed:" + ",".join(failed))

    CLAUDE_WORKFLOW.write_text(
        canonicalize_dispatch_inputs(CLAUDE_WORKFLOW.read_text(encoding="utf-8")),
        encoding="utf-8",
    )

    created_at = now()
    trace_id = str(live.get("trace_id"))

    AGENT_CONTEXT.write_text(
        f"""# AGENT_CONTEXT.md | canonical configuration

Updated: {created_at}
Repository: bereznyi-aleksandr/ai-devops-system
Active protocol: BEM-934
Roadmap state: 9/10 stages complete
Current task: BEM934-CLOSE
Release status: FOLLOW_UP_REQUIRED

## Operational provider architecture

Primary provider for curator, analyst, auditor, and executor: `claude_code`.
Primary workflow: `.github/workflows/claude.yml`.
Operational ingress: Telegram -> Cloudflare Worker -> `provider-router.yml` -> `claude.yml`.

Historical self-hosted Codex paths are disabled and deprecated. They are not an available operational runtime.
`gpt_codex_cloud` is a GitHub-hosted reserve path. It may claim LLM execution only when OpenAI runtime secrets are configured; otherwise it is a clearly labelled `mechanical_fallback`.

## Verified BEM-934 state

Stages 1-8: DONE.
Stage 9 `BEM934-LIVE-TEST`: DONE under strict receipt v2.
Operator trace: `;{trace_id}`.
Provider route: `claude_code` -> `claude.yml`.
Semantic executor transport: `completed`, blocker `null`.
Historical failed attempts remain disclosed.
The prior replay-based contradictory PASS is archived as superseded.

Stage 10 `BEM934-CLOSE`: IN_PROGRESS.
Closure is not approved yet. Release remains `FOLLOW_UP_REQUIRED` until an independent `EXTERNAL_AUDITOR_CLAUDE verdict is PASS/APPROVED and a strict final validator succeeds.

## Canonical evidence

- `governance/proofs/BEM934_live_test_receipt.json`
- `governance/proofs/BEM934_live_test_receipt_superseded_replay.json`
- `governance/roadmap/ACTIVE_QUEUE.json`
- `governance/config/provider_config.json`
- `governance/protocols/BEM934_Protocol.md`

## Closure rule

No top-level PASS may contradict nested transport records. No replay may be represented as operator-authored ingress. Release PASS requires committed proof files, independent external Claude approval, and a final fail-closed validator.
""",
        encoding="utf-8",
    )

    SYSTEM_STATUS.write_text(
        f"""# SYSTEM_STATUS.md | BEM-934

Updated: {created_at}

## Current status

Roadmap: 9/10 stages complete.
Current stage: `BEM934-CLOSE`.
Stage tasks: 1/3 complete after this preparation.
Release: `FOLLOW_UP_REQUIRED`.
Queue: `ACTIVE`.

## Completed LIVE stage

`BEM934-LIVE-TEST` is verified by strict receipt v2:
- operator-authored Telegram evidence bound to trace `;{trace_id}`;
- router selected `claude_code` and dispatched `claude.yml`;
- latest executor transport is `completed` with blocker `null`;
- substantive Claude report exists;
- historical failed transports remain visible;
- old replay-based contradictory PASS is archived as superseded.

## Provider status

`claude_code` is primary for all four roles.
Self-hosted Codex workflows are disabled, deprecated, and non-operational.
`gpt_codex_cloud` is reserve-only and is `mechanical_fallback` without configured OpenAI runtime secrets.

## Remaining closure tasks

1. Canonical context/status and canonical required inputs in `claude.yml` — DONE.
2. Independent `EXTERNAL_AUDITOR_CLAUDEa audit — PENDING.
3. Strict final closure validator and release promotion — PENDING.

Do not assert release PASS before the two pending tasks produce committed proof artifacts.
""",
        encoding="utf-8",
    )

    queue["version"] = int(queue.get("version", 0)) + 1
    queue["updated_at"] = created_at
    queue["queue_state"] = "ACTIVE"
    queue["current_task"] = "BEM934-CLOSE"
    queue["release_status"] = "FOLLOW_UP_REQUIRED"
    for task in queue.get("tasks", []):
        if task.get("id") == "BEM934-CLOSE":
            task["status"] = "IN_PROGRESS"
            task["stage_progress"] = {
                "tasks_done": 1,
                "tasks_total": 3,
                "percent": 33,
                "completed": ["canonical_context_status_and_claude_inputs"],
                "pending": ["external_claude_audit", "strict_final_closure"],
            }
            task["preparation_receipt"] = RECEIPT.as_posix()
    queue["next_action"] = (
        "Run independent EXTERNAL_AUDITOR_CLAUDE audit against committed BEM-934 evidence; "
        "release promotion remains forbidden."
    )
    QUEUE.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    receipt = {
        "status": "PASS",
        "protocol": "BEM-934",
        "task_id": "BEM934-CLOSE",
        "phase": "PREPARED_FOR_EXTERNAL_AUDIT",
        "created_at": created_at,
        "release_promoted": False,
        "roadmap_tasks_done": 9,
        "roadmap_tasks_total": 10,
        "stage_tasks_done": 1,
        "stage_tasks_total": 3,
        "checks": checks,
        "updated_files": [
            AGENT_CONTEXT.as_posix(),
            SYSTEM_STATUS.as_posix(),
            CLAUDE_WORKFLOW.as_posix(),
            QUEUE.as_posix(),
        ],
        "next_action": "Independent EXTERNAL_AUDITOR_CLAUDE audit",
    }
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with EXECUTION_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "timestamp": created_at,
            "task_id": "BEM934-CLOSE.PREPARE",
            "status": "DONE",
            "receipt": RECEIPT.as_posix(),
            "release_promoted": False,
            "next_task": "BEM934-CLOSE.EXTERNAL-AUDIT",
        }, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
