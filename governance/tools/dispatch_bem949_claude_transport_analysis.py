#!/usr/bin/env python3
"""Dispatch one governed, read-only Claude analyst run for BEM-949 transport recovery."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

TRACE_ID = "bem949_claude_transport_recovery_20260624T194500Z"
INPUTS = {
    "role": "analyst",
    "provider": "claude",
    "trace_id": TRACE_ID,
    "cycle_id": "BEM949_TRANSPORT_RECOVERY",
    "task_type": "incident_analysis",
    "task": (
        "Read governance/briefs/BEM949_CLAUDE_TRANSPORT_RECOVERY.md and analyze "
        "the Claude transport-persistence incident. Stay read-only: do not edit or "
        "commit files. Produce the governed trace report with a bounded repair and "
        "verification plan. Preserve the existing BEM-949 P1/P4 blocked status."
    ),
}


def main() -> int:
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    token = os.environ.get("GH_TOKEN", "").strip()
    if not repo or not token:
        raise RuntimeError("GITHUB_REPOSITORY and GH_TOKEN are required")

    body = json.dumps({"ref": "main", "inputs": INPUTS}).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/actions/workflows/claude.yml/dispatches",
        data=body,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "ai-devops-bem949-transport-recovery",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status not in (200, 201, 204):
                raise RuntimeError(f"unexpected HTTP status: {response.status}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Claude dispatch failed: HTTP {exc.code}: {detail}") from exc

    print(f"DISPATCHED_CLAUDE_TRACE={TRACE_ID}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
