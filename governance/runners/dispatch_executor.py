\
#!/usr/bin/env python3
"""BEM-948 dispatch bridge. HTTP 204 means dispatched, never completed."""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DEFAULT = ROOT / "governance/state/dispatch_processed.jsonl"
EXECUTED_DEFAULT = ROOT / "governance/state/dispatch_executed.jsonl"
RECEIPT_DEFAULT = ROOT / "governance/proofs/BEM948_dispatch_executor_receipt.json"
TARGETS = {
    "claude_code": "claude.yml",
    "gpt_codex_cloud": "gpt-codex-cloud.yml",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def dispatch_key(row: dict[str, Any]) -> str:
    return str(row.get("dispatch_id") or row.get("trace_id") or "")


def planned_rows(args: argparse.Namespace, trace_id: str) -> list[dict[str, Any]]:
    if args.plan_file:
        value = json.loads(Path(args.plan_file).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("plan_json_object_required")
        if str(value.get("trace_id") or "") != trace_id:
            raise ValueError("plan_trace_id_mismatch")
        if str(value.get("dispatch_result") or "planned") != "planned":
            raise ValueError("plan_not_planned")
        return [value]

    completed = {dispatch_key(row) for row in load_jsonl(Path(args.executed))}
    rows = [
        row
        for row in load_jsonl(Path(args.processed))
        if row.get("status") == "processed"
        and row.get("dispatch_result") == "planned"
        and str(row.get("trace_id") or row.get("dispatch_id") or "") == trace_id
        and dispatch_key(row) not in completed
    ]
    return rows[: max(1, args.max)]


def build_inputs(row: dict[str, Any], trace_id: str, provider: str) -> dict[str, str]:
    task_id = str(row.get("task_id") or "BEM948-DISPATCH")
    if provider == "gpt_codex_cloud":
        return {"trace_id": trace_id, "task_id": task_id}

    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    role = str(row.get("logical_role") or row.get("role") or "curator")
    return {
        "role": role,
        "provider": "claude",
        "trace_id": trace_id,
        "cycle_id": str(payload.get("cycle_id") or f"dispatch_{trace_id}"),
        "task_type": str(payload.get("task_type") or "default_development"),
        "task": str(payload.get("task") or f"Governance dispatch {trace_id}"),
    }


def dispatch_one(row: dict[str, Any], trace_id: str) -> dict[str, Any]:
    provider = str(row.get("provider_selected") or row.get("provider") or "")
    workflow = str(row.get("target_workflow_id") or "")
    role = str(row.get("logical_role") or row.get("role") or "curator")
    result: dict[str, Any] = {
        "protocol": "BEM-948",
        "task_id": str(row.get("task_id") or "BEM948-DISPATCH"),
        "created_at": utc_now(),
        "dispatch_id": dispatch_key(row),
        "trace_id": trace_id,
        "logical_role": role,
        "provider_selected": provider,
        "target_workflow_id": workflow,
        "dispatch_result": "failed",
        "http_status": None,
        "blocker": None,
    }

    if TARGETS.get(provider) != workflow:
        result["blocker"] = "unsupported_or_mismatched_provider_target"
        return result

    token = os.getenv("AI_SYSTEM_GITHUB_PAT") or os.getenv("GITHUB_TOKEN") or ""
    repo = os.getenv("GITHUB_REPOSITORY") or ""
    if not token or not repo:
        result["blocker"] = "github_dispatch_credentials_or_repository_missing"
        return result

    inputs = build_inputs(row, trace_id, provider)
    result["inputs"] = inputs
    api = os.getenv("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    body = json.dumps({"ref": "main", "inputs": inputs}).encode("utf-8")
    request = urllib.request.Request(
        f"{api}/repos/{repo}/actions/workflows/{workflow}/dispatches",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result["http_status"] = response.status
    except urllib.error.HTTPError as exc:
        result["http_status"] = exc.code
    except Exception:
        result["blocker"] = "network_error"

    if result["http_status"] == 204:
        result["dispatch_result"] = "dispatched"
    elif result["blocker"] is None:
        result["blocker"] = f"workflow_dispatch_http_{result['http_status']}"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="BEM-948 dispatch executor")
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--plan-file")
    parser.add_argument("--max", type=int, default=1)
    parser.add_argument("--processed", default=str(PROCESSED_DEFAULT))
    parser.add_argument("--executed", default=str(EXECUTED_DEFAULT))
    parser.add_argument("--output", default=str(RECEIPT_DEFAULT))
    args = parser.parse_args()
    trace_id = args.trace_id.strip()

    try:
        rows = planned_rows(args, trace_id)
    except Exception as exc:
        rows = []
        discovery_error = f"plan_or_state_error:{type(exc).__name__}"
    else:
        discovery_error = None

    if not trace_id or not rows:
        receipt = {
            "status": "BLOCKED",
            "protocol": "BEM948",
            "task_id": "BEM948-DISPATCH",
            "created_at": utc_now(),
            "trace_filter": trace_id,
            "dispatches": [],
            "blockers": [discovery_error or "matching_planned_dispatch_absent"],
            "next_task": "BEM948-DISPATCH-AUTOREPAIR",
        }
        write_json(Path(args.output), receipt)
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    results = [dispatch_one(row, trace_id) for row in rows]
    append_jsonl(Path(args.executed), results)
    failed = [row for row in results if row["dispatch_result"] != "dispatched"]
    receipt = {
        "status": "DISPATCHED" if not failed else "BLOCKED",
        "protocol": "BEM-948",
        "task_id": str(rows[0].get("task_id") or "BEM948-DISPATCH"),
        "created_at": utc_now(),
        "trace_filter": trace_id,
        "evidence_kind": "dispatch_acknowledgement",
        "runtime_execution_claim": False,
        "dispatched_count": len(results) - len(failed),
        "failed_count": len(failed),
        "dispatches": results,
        "checks": {
            "trace_id_required": True,
            "trace_scope_enforced": True,
            "http_204_means_dispatched_not_completed": True,
        },
        "blockers": [row["blocker"] for row in failed if row.get("blocker")],
        "next_task": "WAIT_FOR_TERMINAL_PROVIDER_RECEIPT"
        if not failed
        else "BEM948-DISPATCH-AUTOREPAIR",
    }
    write_json(Path(args.output), receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
