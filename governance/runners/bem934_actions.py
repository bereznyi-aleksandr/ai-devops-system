#!/usr/bin/env python3
"""BEM-934 request-driven diagnostics."""
from __future__ import annotations
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REQUEST = ROOT / "governance/runtime/bem934_state_request.json"
OUT = ROOT / "governance/proofs/BEM934_binding_run_diagnostic.json"

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def api(url: str, token: str) -> tuple[int, Any]:
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "bem934-run-inspector",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            raw = res.read()
            return res.status, json.loads(raw.decode()) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            data = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            data = {"message": raw[:2000]}
        return exc.code, data
    except Exception as exc:
        return 0, {"type": exc.__class__.__name__, "message": str(exc)[:2000]}

def main() -> int:
    request = json.loads(REQUEST.read_text(encoding="utf-8"))
    action = str(request.get("action") or "")
    token = os.environ.get("BEM934_GITHUB_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    payload: dict[str, Any] = {
        "status": "BLOCKED",
        "protocol": "BEM-934",
        "created_at": now(),
        "action": action,
        "checks": {},
    }
    if action != "inspect_binding_runs":
        payload["blocker"] = "unsupported_diagnostic_action"
    elif not token or not repo:
        payload["blocker"] = "github_token_or_repository_missing"
    else:
        collected = {}
        ok = True
        for workflow in ("bem934-state.yml", "claude.yml"):
            status, data = api(
                f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/runs?per_page=10",
                token,
            )
            runs = []
            if status == 200 and isinstance(data, dict):
                for item in data.get("workflow_runs", []):
                    if not isinstance(item, dict):
                        continue
                    runs.append({
                        "id": item.get("id"),
                        "event": item.get("event"),
                        "status": item.get("status"),
                        "conclusion": item.get("conclusion"),
                        "head_sha": item.get("head_sha"),
                        "created_at": item.get("created_at"),
                        "updated_at": item.get("updated_at"),
                        "run_number": item.get("run_number"),
                    })
            else:
                ok = False
            collected[workflow] = {"http_status": status, "runs": runs}
        payload["workflows"] = collected
        payload["checks"] = {
            "state_runs_readable": collected["bem934-state.yml"]["http_status"] == 200,
            "claude_runs_readable": collected["claude.yml"]["http_status"] == 200,
        }
        payload["status"] = "PASS" if ok else "BLOCKED"
        if not ok:
            payload["blocker"] = "workflow_runs_api_unavailable"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
