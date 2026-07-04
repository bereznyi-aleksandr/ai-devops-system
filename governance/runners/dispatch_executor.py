#!/usr/bin/env python3
"""Trace-bound GitHub Actions lifecycle observer for BEM949-DSM-1.

The HTTP 204 only acknowledges a workflow-dispatch request. Completion requires a
matching workflow run with a terminal conclusion.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LIFECYCLE_LOG = ROOT / "governance/state/dispatch_lifecycle.jsonll"
TASK_ID = "BEM949-DSM-1"
WORKFLOW_ID = "dsm1-lifecycle-probe.yml"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def append_event(value: dict[str, Any]) -> None:
    LIFECYCLE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with LIFECYCLE_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def lifecycle_event(
    trace_id: str,
    workflow_id: str,
    state: str,
    **extra: object,
) -> dict[str, Any]:
    return {
        "protocol": "BEM-949",
        "task_id": TASK_ID,
        "observed_at": now(),
        "trace_id": trace_id,
        "workflow_id": workflow_id,
        "state": state,
        **extra,
    }


def api_get(url: str, token: str) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "ai-devops-dsm1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8", "replace")
            payload = json.loads(raw) if raw else {}
            return response.status, payload if isinstance(payload, dict) else {}
    except urllib.error.HTTPError as exc:
        return exc.code, {}
    except Exception as exc:
        return 0, {"error": type(exc).__name__}


def run_matches_trace(run: dict[str, Any], trace_id: str) -> bool:
    return trace_id in " ".join(
        str(run.get(field) or "")
        for field in ("display_title", "name", "path")
    )


def blocked(
    output_path: Path,
    trace_id: str,
    blocker: str,
    *,
    run_id: int | None = None,
    http_status: int | None = None,
) -> int:
    result: dict[str, Any] = {
        "status": "BLOCKED",
        "task_id": TASK_ID,
        "trace_id": trace_id,
        "result": {"blocker": blocker, "run_id": run_id},
    }
    if http_status is not None:
        result["result"]["last_http_status"] = http_status
    write_json(output_path, result)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-only", action="store_true)
    parser.add_argument("--record-dispatched", action="store_true")
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--dispatch-id", required=True)
    parser.add_argument("--workflow-id", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--poll-timeout-seconds", type=int, default=300)
    parser.add_argument("--poll-interval-seconds", type=int, default=5)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output_path = Path(args.output)
    if not args.confirm_only:
        return blocked(output_path, args.trace_id, "confirm_only_required")
    if args.dispatch_id != TASK_ID or args.workflow_id != WORKFLOW_ID:
        return blocked(output_path, args.trace_id, "invalid_lifecycle_identity")

    token = (
        os.getenv("GITHUB_TOKEN")
        or os.getenv("GH_TOKEN")
        or os.getenv("AI_SYSTEM_GITHUB_PAT")
        or ""
    )
    if not token or not args.repository:
        return blocked(
            output_path,
            args.trace_id,
            "confirm_credentials_repository_or_workflow_missing",
        )

    if args.record_dispatched:
        append_event(
            lifecycle_event(
                args.trace_id,
                args.workflow_id,
                "DISPATCHED",
                http_status=204,
            )
        )

    api_root = os.getenv("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    encoded_workflow = urllib.parse.quote(args.workflow_id, safe="")
    url = (
        f"{api_root}/repos/{args.repository}/actions/workflows/{encoded_workflow}/runs"
        "?event=workflow_dispatch&per_page=100"
    )

    deadline = time.monotonic() + max(1, args.poll_timeout_seconds)
    observed_run_id: int | None = None
    last_http_status: int | None = None

    while time.monotonic() < deadline:
        http_status, payload = api_get(url, token)
        last_http_status = http_status
        runs = (
            payload.get("workflow_runs", [])
            if http_status == 200 and isinstance(payload, dict)
            else []
        )
        candidate = next(
            (
                run
                for run in runs
                if isinstance(run, dict) and run_matches_trace(run, args.trace_id)
            ),
            None,
        )

        if candidate is not None:
            run_id = candidate.get("id")
            if isinstance(run_id, int) and observed_run_id is None:
                observed_run_id = run_id
                append_event(
                    lifecycle_event(
                        args.trace_id,
                        args.workflow_id,
                        "START_CONFIRMED",
                        run_id=run_id,
                        github_status=candidate.get("status"),
                        html_url=candidate.get("html_url"),
                    )
                )

            if candidate.get("status") == "completed":
                conclusion = str(candidate.get("conclusion") or "unknown")
                terminal_state = (
                    "COMPLETED" if conclusion == "success" else "FAILED"
                )
                append_event(
                    lifecycle_event(
                        args.trace_id,
                        args.workflow_id,
                        terminal_state,
                        run_id=observed_run_id,
                        conclusion=conclusion,
                        html_url=candidate.get("html_url"),
                    )
                )
                append_event(
                    lifecycle_event(
                        args.trace_id,
                        args.workflow_id,
                        "STATE_COMMITED",
                        run_id=observed_run_id,
                        terminal_state=terminal_state,
                        conclusion=conclusion,
                        commit_scope="dispatch_lifecycle_log",
                    )
                )
                write_json(
                    output_path,
                    {
                        "status": "STATE_COMMITTED",
                        "task_id": TASK_ID,
                        "trace_id": args.trace_id,
                        "result": {
                            "terminal_state": termal_state,
                            "conclusion": conclusion,
                            "run_id": observed_run_id,
                            "html_url": candidate.get("html_url"),
                        },
                    },
                )
                return 0 if conclusion == "success" else 1

        time.sleep(max(1, args.poll_interval_seconds))

    return blocked(
        output_path,
        args.trace_id,
        "start_or_terminal_state_not_observed_before_timeout",
        run_id=observed_run_id,
        http_status=last_http_status,
    )


if __name__ == "__main__":
    raise SystemExit(main())
