#!/usr/bin/env python3
"""BEM-934 proof-bearing object runtime binding probe."""
from __future__ import annotations

import base64
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
REQUEST = ROOT / "governance/runtime/bem934_state_request.json"
PROOFS = ROOT / "governance/proofs"
REGISTRY = ROOT / "governance/architecture/objects_registry_v2.json"
RECEIPT = PROOFS / "BEM934_objects_bound_receipt.json"
PLAN_REPO_PATH = "governance/proofs/BEM934_object_binding_plan.json"
TRANSPORT_REPO_PATH = "governance/transport/results.jsonl"

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def api(method: str, url: str, token: str, payload: dict[str, Any] | None = None) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "bem934-object-binding-probe",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            return response.status, json.loads(raw.decode("utf-8")) if raw else None
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = {"message": raw[:2000]}
        return error.code, parsed
    except Exception as error:
        return 0, {"error_type": error.__class__.__name__, "message": str(error)[:2000]}

def contents_url(repository: str, repo_path: str) -> str:
    return f"https://api.github.com/repos/{repository}/contents/{urllib.parse.quote(repo_path, safe='/')}?ref=main"

def read_repo_file(repository: str, token: str, repo_path: str) -> tuple[int, dict[str, Any] | None, bytes | None]:
    status, payload = api("GET", contents_url(repository, repo_path), token)
    if status != 200 or not isinstance(payload, dict):
        return status, payload if isinstance(payload, dict) else None, None
    try:
        decoded = base64.b64decode(str(payload.get("content", "")))
    except (ValueError, TypeError):
        return status, payload, None
    return status, payload, decoded

def workflow_runs_url(repository: str) -> str:
    return f"https://api.github.com/repos/{repository}/actions/workflows/claude.yml/runs?event=workflow_dispatch&per_page=30"

def plan_commit_sha(repository: str, token: str) -> str | None:
    query = urllib.parse.urlencode({"path": PLAN_REPO_PATH, "sha": "main", "per_page": 1})
    status, payload = api("GET", f"https://api.github.com/repos/{repository}/commits?{query}", token)
    if status == 200 and isinstance(payload, list) and payload and isinstance(payload[0], dict):
        value = payload[0].get("sha")
        return str(value) if value else None
    return None

def semantic_checks(plan: dict[str, Any], trace_id: str) -> dict[str, bool]:
    required = ("objective", "assumptions", "steps", "acceptance", "risks", "trace_id")
    text = json.dumps(plan, ensure_ascii=False).lower()
    steps = plan.get("steps")
    acceptance = plan.get("acceptance")
    historical = {"verify objective", "prepare execution boundary", "request auditor pre-check"}
    normalized = {str(item).strip().lower() for item in steps} if isinstance(steps, list) else set()
    return {
        "required_fields_present": all(field in plan for field in required),
        "trace_matches": plan.get("trace_id") == trace_id,
        "steps_are_task_specific": isinstance(steps, list) and len([x for x in steps if str(x).strip()]) >= 3,
        "acceptance_is_verifiable": isinstance(acceptance, list) and len([x for x in acceptance if str(x).strip()]) >= 2,
        "mentions_wrk_c1": "wrk-c1" in text or "wrk_c1" in text,
        "mentions_claude_provider": "claude" in text,
        "mentions_object_runtime_binding": "object" in text and "runtime" in text and "binding" in text,
        "mentions_idempotent_telegram_routing": "idempotent" in text and "telegram" in text and "routing" in text,
        "historical_fixed_plan_absent": normalized != historical,
    }

def find_transport_result(repository: str, token: str, trace_id: str) -> tuple[dict[str, Any] | None, str | None]:
    status, metadata, raw = read_repo_file(repository, token, TRANSPORT_REPO_PATH)
    if status != 200 or metadata is None or raw is None:
        return None, None
    found = None
    for line in raw.decode("utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and item.get("trace_id") == trace_id:
            found = item
    return found, str(metadata.get("sha")) if metadata.get("sha") else None

def run_probe() -> int:
    token = os.environ.get("BEM934_GITHUB_TOKEN", "").strip()
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    run_id = os.environ.get("GITHUB_RUN_ID", "manual").strip()
    trace_id = f"bem934_objects_bound_{run_id}"
    receipt: dict[str, Any] = {
        "status": "BLOCKED", "protocol": "BEM-934", "task_id": "BEM934-OBJECTS-BOUND",
        "created_at": utc_now(), "trace_id": trace_id, "provider_selected": "claude_code",
        "workflow_id": "claude.yml", "plan_path": PLAN_REPO_PATH, "checks": {}, "missing": [],
    }
    if not token or not repository:
        receipt["blocker"] = "github_token_or_repository_missing"
        write_json(RECEIPT, receipt)
        return 0

    before_status, before_payload = api("GET", workflow_runs_url(repository), token)
    before_ids: set[int] = set()
    if before_status == 200 and isinstance(before_payload, dict):
        before_ids = {int(x["id"]) for x in before_payload.get("workflow_runs", []) if isinstance(x, dict) and x.get("id")}

    task = (
        "BEM-934 object runtime binding proof. Create exactly "
        f"{PLAN_REPO_PATH} as strict JSON with fields objective, assumptions, steps, acceptance, risks, trace_id. "
        f"Set trace_id exactly to {trace_id}. The objective and plan must explicitly cover WRK-C1, the Claude provider, "
        "object runtime binding, and idempotent Telegram routing. Include at least three task-specific implementation or "
        "verification steps and at least two independently verifiable acceptance checks. Do not use the historical generic "
        "three-step plan. Commit and push this proof file to main. Do not modify application code, ACTIVE_QUEUE, objects "
        "registry, or unrelated files."
    )
    dispatch_status, dispatch_payload = api(
        "POST",
        f"https://api.github.com/repos/{repository}/actions/workflows/claude.yml/dispatches",
        token,
        {"ref": "main", "inputs": {
            "role": "analyst", "provider": "claude", "trace_id": trace_id,
            "cycle_id": trace_id, "task_type": "object_runtime_binding", "task": task,
        }},
    )
    receipt["dispatch_http_status"] = dispatch_status
    if dispatch_status != 204:
        receipt["blocker"] = "claude_workflow_dispatch_failed"
        receipt["dispatch_error"] = dispatch_payload
        write_json(RECEIPT, receipt)
        return 0

    observed_run = None
    plan = None
    plan_metadata = None
    transport_result = None
    transport_blob_sha = None
    deadline = time.time() + 1500
    while time.time() < deadline:
        runs_status, runs_payload = api("GET", workflow_runs_url(repository), token)
        if runs_status == 200 and isinstance(runs_payload, dict):
            candidates = [x for x in runs_payload.get("workflow_runs", []) if isinstance(x, dict) and x.get("id") and int(x["id"]) not in before_ids]
            if candidates:
                c = candidates[0]
                observed_run = {k: c.get(k) for k in ("id", "status", "conclusion", "head_sha", "created_at", "updated_at")}
        content_status, metadata, raw = read_repo_file(repository, token, PLAN_REPO_PATH)
        if content_status == 200 and metadata is not None and raw is not None:
            try:
                candidate = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                candidate = None
            if isinstance(candidate, dict) and candidate.get("trace_id") == trace_id:
                plan, plan_metadata = candidate, metadata
        transport_result, transport_blob_sha = find_transport_result(repository, token, trace_id)
        complete = observed_run is not None and observed_run.get("status") == "completed"
        if plan is not None and transport_result is not None and complete:
            break
        if complete and observed_run.get("conclusion") not in ("success", None):
            break
        time.sleep(15)

    receipt["github_workflow"] = observed_run
    receipt["transport_result"] = transport_result
    receipt["transport_blob_sha"] = transport_blob_sha
    if plan is None or plan_metadata is None:
        receipt["blocker"] = "trace_specific_plan_not_created"
        write_json(RECEIPT, receipt)
        return 0

    commit_sha = plan_commit_sha(repository, token)
    plan_blob_sha = str(plan_metadata.get("sha")) if plan_metadata.get("sha") else None
    semantic = semantic_checks(plan, trace_id)
    checks = {
        "dispatch_accepted": dispatch_status == 204,
        "github_hosted_claude_run_observed": bool(observed_run),
        "github_hosted_claude_run_completed": bool(observed_run and observed_run.get("status") == "completed"),
        "github_hosted_claude_run_success": bool(observed_run and observed_run.get("conclusion") == "success"),
        "transport_result_observed": bool(transport_result),
        "transport_result_completed": bool(isinstance(transport_result, dict) and transport_result.get("status") == "completed"),
        "transport_result_unblocked": bool(isinstance(transport_result, dict) and not transport_result.get("blocker")),
        "transport_commit_sha_present": bool(isinstance(transport_result, dict) and transport_result.get("commit_sha")),
        "plan_blob_sha_present": bool(plan_blob_sha),
        "plan_commit_sha_present": bool(commit_sha),
        **semantic,
    }
    receipt.update({
        "checks": checks,
        "semantic_verdict": "PASS" if all(semantic.values()) else "REJECT",
        "plan_blob_sha": plan_blob_sha,
        "commit_sha": commit_sha,
        "missing": [key for key, value in checks.items() if not value],
    })
    if not all(checks.values()):
        receipt["blocker"] = "binding_evidence_incomplete"
        write_json(RECEIPT, receipt)
        return 0

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    bound_at = utc_now()
    registry.update({
        "protocol": "BEM-934",
        "status": "BOUND",
        "bound_at": bound_at,
        "binding_evidence": {
            "trace_id": trace_id,
            "provider_selected": "claude_code",
            "workflow_id": "claude.yml",
            "workflow_run_id": observed_run.get("id") if observed_run else None,
            "plan_path": PLAN_REPO_PATH,
            "plan_blob_sha": plan_blob_sha,
            "commit_sha": commit_sha,
            "transport_blob_sha": transport_blob_sha,
            "transport_commit_sha": transport_result.get("commit_sha"),
            "semantic_verdict": "PASS",
            "semantic_checks": semantic,
        },
    })
    notes = list(registry.get("notes", []))
    note = "BEM-934 runtime binding proven by a committed trace-specific Claude WRK-C1 plan, transport completion, and semantic validation."
    if note not in notes:
        notes.append(note)
    registry["notes"] = notes
    write_json(REGISTRY, registry)

    receipt.update({"status": "PASS", "bound_at": bound_at, "registry_path": str(REGISTRY.relative_to(ROOT)), "registry_status": "BOUND"})
    receipt.pop("blocker", None)
    write_json(RECEIPT, receipt)
    return 0

ACTIONS = {"objects_binding_probe": run_probe}

def main() -> int:
    request = json.loads(REQUEST.read_text(encoding="utf-8"))
    action = str(request.get("action") or "").strip()
    handler = ACTIONS.get(action)
    if handler is None:
        write_json(PROOFS / "BEM934_state_action_blocked_receipt.json", {
            "status": "BLOCKED", "protocol": "BEM-934", "created_at": utc_now(),
            "action": action, "blocker": "unsupported_action",
        })
        return 1
    return handler()

if __name__ == "__main__":
    raise SystemExit(main())
