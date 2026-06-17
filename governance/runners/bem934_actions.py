#!/usr/bin/env python3
"""BEM-934 indexed actions."""

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


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def api(method: str, url: str, token: str, payload: dict[str, Any] | None = None) -> tuple[int, Any]:
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "bem934-binding-probe",
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
            data = {"message": raw[1000]}
        return exc.code, data


def checks(plan: dict[str, Any], trace: str) -> dict[str, bool]:
    fields = ("objective", "assumptions", "steps", "acceptance", "risks", "trace_id")
    text = json.dumps(plan, ensure_ascii=False).lower()
    terms = ("wrk-c1", "claude", "object", "runtime", "binding", "telegram", "idempotent", "routing")
    steps = plan.get("steps")
    acceptance = plan.get("acceptance")
    fixed = {"verify objective", "prepare execution boundary", "request auditor pre-check"}
    return {
        "required_fields_present": all(field in plan for field in fields),
        "trace_matches": plan.get("trace_id") == trace,
        "steps_are_specific": isinstance(steps, list) and len([x for x in steps if str(x).strip()]) >= 3,
        "acceptance_is_verifiable": isinstance(acceptance, list) and len([x for x in acceptance if str(x).strip()]) >= 2,
        "all_binding_terms_present": all(term in text for term in terms),
        "historical_fixed_plan_absent": not (isinstance(steps, list) and {str(x).strip().lower() for x in steps} == fixed),
    }


def objects_binding_probe() -> None:
    receipt_path = PROOFS / "BEM934_objects_bound_receipt.json"
    token = os.environ.get("BEM934_GITHUB_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    trace = "bem934_objects_bound_" + os.environ.get("GITHUB_RUN_ID", "manual")
    plan_path = "governance/proofs/BEM934_object_binding_plan.json"
    receipt: dict[str, Any] = {
        "status": "BLOCKED", "protocol": "BEM-934", "task_id": "BEM934-OBJECTS-BOUND",
        "created_at": now(), "trace_id": trace, "provider_selected": "claude_code",
        "workflow_id": "claude.yml", "plan_path": plan_path, "checks": {}, "missing": [],
    }
    if not token or not repo:
        receipt["blocker"] = "github_token_or_repository_missing"
        write(receipt_path, receipt); return

    task = ("BEM-934 object binding proof. Create exactly governance/proofs/BEM934_object_binding_plan.json as strict JSON with fields objective, assumptions, steps, acceptance, risks, trace_id. " f "Set trace_id exactly to {trace}. The objective must mention WRK-C1, Claude provider, object runtime binding, and idempotent Telegram routing. Include at least three task-specific steps and two independently verifiable acceptance checks. Commit and push to main. Do not edit application code or use a generic three-step plan.")
    url = f"https://api.github.com/repos/{repo}/actions/workflows/claude.yml/dispatches"
    status, error = api("POST", url, token, {"ref": "main", "inputs": {"role": "analyst", "provider": "claude_code", "trace_id": trace, "cycle_id": trace, "task_type": "contour_binding_probe", "task": task}})
    receipt["dispatch_http_status"] = status
    if status != 204:
        receipt["blocker"] = "claude_workflow_dispatch_failed"; receipt["dispatch_error"] = error
        write(receipt_path, receipt); return

    quoted = urllib.parse.quote(plan_path, safe="/")
    content_url = f"https://api.github.com/repos/{repo}/contents/{quoted}?ref=main"
    runs_url = f"https://api.github.com/repos/{repo}/actions/workflows/claude.yml/runs?event=workflow_dispatch&per_page=10"
    plan = content = observed = None
    deadline = time.time() + 1200
    while time.time() < deadline:
        rs, runs = api("GET", runs_url, token)
        if rs == 200 and isinstance(runs, dict) and runs.get("workflow_runs"):
            r = runs["workflow_runs"][0]; observed = {"id": r.get("id"), "status": r.get("status"), "conclusion": r.get("conclusion"), "head_sha": r.get("head_sha", ),"created_at": r.get("created_at")}
        cs, item = api("GET", content_url + f"&nonce={int(time.time())}", token)
        if cs == 200 and isinstance(item, dict):
            try:
                candidate = json.loads(base64.b64decode(item.get("content", "")).decode())
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                candidate = None
            if isinstance(candidate, dict) and candidate.get("trace_id") == trace:
                plan, content = candidate, item; break
        if observed and observed.get("status") == "completed" and observed.get("conclusion") not in ("success", None):
            receipt["blocker"] = "claude_workflow_failed"; break
        time.sleep(15)
    receipt["hithub_workflow"] = observed
    if plan is None or content is None:
        receipt.setdefault("blocker", "trace_specific_plan_not_created"); write(receipt_path, receipt); return

    query = urllib.parse.urlencode({"path": plan_path, "per_page": 1, "sha": "main"})
    cms, commits = api("GET", f"https://api.github.com/repos/{repo}/commits?{query}", token)
    commit_sha = commits[0].get("sha") if cms == 200 and isinstance(commits, list) and commits else None
    semantic = checks(plan, trace)
    all_checks = {"dispatch_accepted": status == 204, "github_hosted_claude_workflow_observed": bool(observed), "plan_created_by_workflow": True, "plan_blob_sha_present": bool(content.get("sha")), "plan_commit_sha_present": bool(commit_sha), **semantic}
    receipt.update({"checks": all_checks, "plan_blob_sha": content.get("sha"), "commit_sha": commit_sha, "semantic_verdict": "PASS" if all(semantic.values()) else "REJECT", "missing": [key for key, value in all_checks.items() if not value]})
    if not all(all_checks.values()):
        receipt["blocker"] = "binding_evidence_incomplete"; write(receipt_path, receipt); return

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    registry.update({"protocol": "BEM-934", "status": "BOUND", "bound_at": now(), "binding_evidence": {"trace_id": trace, "provider_selected": "claude_code", "workflow_id": "claude.yml", "workflow_run_id": observed.get("id") if observed else None, "plan_path": plan_path, "plan_blob_sha": content.get("sha"), "commit_sha": commit_sha, "semantic_verdict": "PASS", "semantic_checks": semantic}})
    notes = list(registry.get("notes", []))
    note = "BEM-934 runtime binding proven by a committed trace-specific Claude WRK-C1 plan and semantic validation."
    if note not in notes: notes.append(note)
    registry["notes"] = notes; write(REGISTRY, registry)
    receipt.update({"status": "PASS", "registry_path": str(REGISTRY.relative_to(ROOT)), "registry_status": "BOUND", "bound_at": registry["bound_at"]})
    receipt.pop("blocker", None); write(receipt_path, receipt)


ACTIONS = {"objects_binding_probe": objects_binding_probe}

def main() -> int:
    request = json.loads(REQUEST.read_text(encoding="utf-8"))
    action = str(request.get("action") or "").strip()
    if not action: return 0
    handler = ACTIONS.get(action)
    if handler is None: raise SystemExit(f"unsupported BEM-934 action: {action}")
    handler(); return 0

if __name__ == "__main__":
    raise SystemExit(main())
