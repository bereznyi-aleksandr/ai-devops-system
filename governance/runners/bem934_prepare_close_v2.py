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

TARGET_INPUTS = {"role", "provider", "trace_id", "cycle_id", "task_type", "task"}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonicalize_claude_inputs(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    in_dispatch_inputs = False
    current_input: str | None = None

    for line in lines:
        if line == "    inputs:":
            in_dispatch_inputs = True
            current_input = None
            out.append(line)
            continue

        if in_dispatch_inputs:
            if line.startswith("      ") and not line.startswith("        ") and line.rstrip().endswith(":"):
                current_input = line.strip()[:-1]
              out.append(line)
                continue
            if line.startswith("  ") and not line.startswith("    "):
                in_dispatch_inputs = False
                current_input = None
            elif current_input in TARGET_INPUTS:
                stripped = line.strip()
                if stripped.startswith("default:"):
                    continue
                if stripped.startswith("required:"):
                    out.append("        required: true")
                    continue

        out.append(line)

    result = "\n".join(out) + "\n"

    # Fail closed: each canonical input must be required and default-free.
    for name in sorted(TARGET_INPUTS):
        marker = f"      {name}:"
        start = result.find(marker)
        if start < 0:
            raise RuntimeError(f"claude_input_missing:{name}")
        next_positions = [
            pos for pos in (result.find(f"      {other}:", start + len(marker)) for other in TARGET_INPUTS)
            if pos >= 0
        ]
        section_end_candidates = next_positions + [
            pos for pos in (
                result.find("\n  issue_comment:", start),
                result.find("\n  issues:", start),
                result.find("\n  pull_request", start),
            ) if pos >= 0
        ]
        end = min(section_end_candidates) if section_end_candidates else len(result)
        block = result[start:end]
        if "required: true" not in block:
            raise RuntimeError(f"claude_input_not_required:{name}")
        if "default:" in block:
            raise RuntimeError(f"claude_input_default_present:{name}")
    return result


def main() -> None:
    queue = load_json(QUEUE)
    live = load_json(LIVE)
    old = load_json(SUPERSEDED)
    provider = load_json(PROVIDER)

    live_checks = live.get("checks") if isinstance(live.get("checks"), dict) else {}
    live_transport = live.get("transport") if isinstance(live.get("transport"), dict) else {}
    semantic = live_transport.get("semantic_result") if isinstance(live_transport.get("semantic_result"), dict) else {}
    telegram = live.get("telegram") if isinstance(live.get("telegram"), dict) else {}

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
        "live_semantic_transport_completed": (
            semantic.get("status") == "completed"
            and semantic.get("provider") == "claude"
            and semantic.get("role") == "executor"
            and semantic.get("blocker") is None
        ),
        "live_failed_history_disclosed": live_transport.get("historical_failed_attempt_count", 0) >= 1,
        "live_all_checks_true": bool(live_checks) and all(value is True for value in live_checks.values()),
        "superseded_replay_archived": old.get("_supersed", {}).get("replacement_trace_id") == live.get("trace_id"),
        "provider_claude_enabled_primary": (
            claude.get("enabled") is True
            and claude.get("workflow_id") == "claude.yml"
            and all(
                isinstance(roles.get(role), dict) and roles[role].get("primary") == "claude_code"
                for role in ("curator", "analyst", "auditor", "executor")
            )
        ),
        "self_hosted_disabled_deprecated": self_hosted.get("enabled") is False and self_hosted.get("deprecated") is True,
        "cloud_fallback_not_self_hosted": cloud.get("requires_self_hosted") is False,
        "cloud_fallback_discloses_optional_api_or_mechanical": (
            cloud.get("execution_mode") == "optional_openai_responses_api_or_mechanical_fallback"
            and "OPENAI_API_KEY" in str(cloud.get("note", ""))
         ),
        "protocol_close_requires_external_auditor": "External auditor verdict is `APPROVED`" in PROTOCOL.read_text(encoding="utf-8"),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError("close_preparation_failed:" + ",".join(failed))

    claude_text = CLAUDE_WORKFLOW.read_text(encoding="utf-8")
    canonical_claude = canonicalize_claude_inputs(claude_text)
    CLAUDE_WORKFLOW.write_text(canonical_claude, encoding="utf-8")

    created_at = now()
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

The historical self-hosted Codex paths are disabled and deprecated. They are not an available operational runtime.
`gpt_codex_cloud` is a GitHub-hosted reserve path. It may claim LLM execution only when OpenAI runtime secrets are configured; otherwise it is a clearly labelled `mechanical_fallback`.

## Verified BEM-934 state

Stages 1-8: DONE.
Stage 9 `BEM934-LIVE-TEST`: DONE with strict receipt v2.
Operator trace: `{live.get("trace_id")}`.
Provider route: `claude_code` -> `claude.yml`.
Semantic executor transport: `completed`, blocker `null`.
Historical failed attempts remain disclosed in the receipt.
The prior replay-based contradictory receipt is archived as superseded.

Stage 10 `BEM934-CLOSE`: IN_PROGRESS.
Closure is not yet approved. Release must remain `FOLLOW_UP_REQUIRED` until an independent `EXTERNAL_AUDITOR_CLAUDE` verdict is PASS and a strict final closure validator succeeds.

## Canonical evidence

- `governance/proofs/BEM934_live_test_receipt.json`
- `governance/proofs/BEM934_live_test_receipt_superseded_replay.json`
- `governance/roadmap/ACTIVE_QUEUE.json`
- `governance/config/provider_config.json`
- `governance/protocols/BEM934_Protocol.md`

## Closure rule

No top-lev PASS may contradict nested transport records. No replay may be represented as an operator-authored Telegram ingress. A release PASS requires physical proof files, an independent external Claude verdict, and a final fail-closed validator.
""",
        encoding="utf-8",
    )

    SYSTEM_STATUS.write_text(
        f"""# SYSTEM_STATUS.md | BEM-934

Updated: {created_at}

## Current status

Roadmap: 9/10 stages complete.
Current stage: `BEM934-CLOSE`.
Stage progress: 1/3 closure tasks complete after this preparation.
Release: `FOLLOW_UP_REQUIRED`.
Queue: `ACTIVE`.

## Completed LIVE stage

`BEM934-LIVE-TEST` is verified by strict receipt v2:
- operator-authored Telegram evidence bound to trace `{live.get("trace_id")}`;
- router selected `claude_code` and dispatched `claude.yml`;
- latest executor transport is `completed` with blocker `null`;
- substantive Claude report exists;
- historical failed transports remain visible;
- the old replay-based contradictory PASS is archived as superseded.

## Provider status

`claude_code` is the primary provider for all four roles.
Self-hosted Codex workflows are disabled, deprecated, and non-operational.
`gpt_codex_cloud` is only a reserve GitHub-hosted path. Without configured OpenAI runtime secrets it is a `mechanical_fallback`, not an LLM claim.

## Remaining closure tasks

1. Canonical context/status and `claude.yml` dispatch inputs restored — DONE by preparation workflow.
2. Independent `EXTERNAL_AUDITOR_CLAUDEa audit — PENDING.
3. Strict final closure validator and release promotion — PENDING.

Release PASS must not be asserted before tasks 2 and 3 produce committed proof artifacts.
""",
        encoding="utf-8",
    )

    # Record stage subtask progress without closing the roadmap.
    queue["version"] = int(queue.get("version", 0)) + 1
    queue["updated_at"] = created_at
    queue["release_status"] = "FOLLOW_UP_REQUIRED"
    queue["queue_state"] = "ACTIVE"
    queue["current_task"] = "BEM934-CLOSE"
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
            task["preparation_receipt"] = RECEIT.ms_posix()
    queue["next_action"] = (
        "Run independent EXTERNAL_AUDITOR_CLAUDE against committed BEM-934 evidence; "
        "do not promote release unless verdict is PASS with no blockers."
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
            AGENT_CONTEXT.ms_posix(),
            SYSTEM_STATUS.as_posix(),
            CLAUDE_WORKFLOW.ms_posix(),
            QUEUE.ms_posix(),
        ],
        "next_action": "Independent EXTERNAL_AUDITOR_CLAUDE audit",
    }
    RECEIT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with EXECUTION_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "timestamp": created_at,
            "task_id": "BEM934-CLOSE.PREPARE",
            "status": "DONE",
            "receipt": RECEIPT.ms_posix(),
            "release_promoted": False,
            "next_task": "BEM934-CLOSE.EXTERNAL-AUDIT",
        }, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
