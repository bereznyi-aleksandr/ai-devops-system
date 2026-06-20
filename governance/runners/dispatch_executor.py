#!/usr/bin/env python3
"""BEM-948 dispatch bridge. HTTP 204 means dispatched, not completed."""
import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "governance/state/dispatch_processed.jsonl"
EXECUTED = ROOT / "governance/state/dispatch_executed.jsonl"
RECEIPT = ROOT / "governance/proofs/BEM948_dispatch_executor_receipt.json"
TARGETS = {
    "claude_code": ("claude.yml", True),
    "gpt_codex_cloud": ("gpt-codex-cloud.yml", False),
}

def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def jsonl(path):
    out = []
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    out.append(value)
            except json.JSONDecodeError:
                pass
    return out

def key(row):
    return str(row.get("dispatch_id") or row.get("trace_id") or "")

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def append(path, rows):
    if rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

def candidates(args, trace):
    if args.plan_file:
        row = json.loads(Path(args.plan_file).read_text(encoding="utf-8"))
        if not isinstance(row, dict) or str(row.get("trace_id") or "") != trace:
            raise ValueError("plan_trace_id_mismatch")
        if str(row.get("dispatch_result") or "planned") != "planned":
            raise ValueError("plan_not_planned")
        return [row]
    done = {key(row) for row in jsonl(Path(args.executed))}
    return [
        row for row in jsonl(Path(args.processed))
        if row.get("status") == "processed"
        and row.get("dispatch_result") == "planned"
        and str(row.get("trace_id") or row.get("dispatch_id") or "") == trace
        and key(row) not in done
    ][:max(1, args.max)]

def dispatch(row, trace):
    provider = str(row.get("provider_selected") or row.get("provider") or "")
    workflow = str(row.get("target_workflow_id") or "")
    role = str(row.get("logical_role") or row.get("role") or "curator")
    result = {
        "protocol": "BEM-948",
        "task_id": str(row.get("task_id") or "BEM948-DISPATCH"),
        "created_at": now(),
        "dispatch_id": key(row),
        "trace_id": trace,
        "logical_role": role,
        "provider_selected": provider,
        "target_workflow_id": workflow,
        "dispatch_result": "failed",
        "http_status": None,
        "blocker": None,
    }
    target = TARGETS.get(provider)
    if not target or workflow != target[0]:
        result["blocker"] = "unsupported_or_mismatched_provider_target"
        return result
    token = os.getenv("AI_SYSTEM_GITHUB_PAT") or os.getenv("GITHUB_TOKEN") or ""
    repo = os.getenv("GITHUB_REPOSITORY", "")
    if not token or not repo:
        result["blocker"] = "github_dispatch_credentials_or_repository_missing"
        return result
    body = {"ref": "main"}
    if target[1]:
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        body["inputs"] = {
            "role": role,
            "provider": "claude",
            "trace_id": trace,
            "cycle_id": str(payload.get("cycle_id") or f"dispatch_{trace}"),
            "task_type": str(payload.get("task_type") or "default_development"),
            "task": str(payload.get("task") or f"Governance dispatch {trace}"),
        }
        result["inputs"] = body["inputs"]
    request = urllib.request.Request(
        f"{os.getenv('GITHUB_API_URL', 'https://api.github.com').rstrip('/')}/repos/{repo}/actions/workflows/{workflow}/dispatches",
        data=json.dumps(body).encode("utf-8"),
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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--max", type=int, default=1)
    parser.add_argument("--plan-file")
    parser.add_argument("--processed", default=str(PROCESSED))
    parser.add_argument("--executed", default=str(EXECUTED))
    parser.add_argument("--output", default=str(RECEIPT))
    args = parser.parse_args()
    trace = args.trace_id.strip()
    output = Path(args.output)
    try:
        rows = candidates(args, trace)
    except Exception as exc:
        rows = []
        error = f"plan_or_state_error:{type(exc).__name__}"
    else:
        error = None
    if not trace or not rows:
        receipt = {
            "status": "BLOCKED",
            "protocol": "BEM-948",
            "task_id": "BEM948-DISPATCH",
            "created_at": now(),
            "trace_filter": trace,
            "dispatches": [],
            "blockers": [error or "matching_planned_dispatch_absent"],
            "next_task": "BEM948-DISPATCH-AUTOREPAIR",
        }
        save(output, receipt)
        print(json.dumps(receipt, ensure_ascii=False))
        raise SystemExit(1)
    results = [dispatch(row, trace) for row in rows]
    append(Path(args.executed), results)
    failed = [row for row in results if row["dispatch_result"] != "dispatched"]
    receipt = {
        "status": "DISPATCHED" if not failed else "BLOCKED",
        "protocol": "BEM-948",
        "task_id": str(rows[0].get("task_id") or "BEM948-DISPATCH"),
        "created_at": now(),
        "trace_filter": trace,
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
        "next_task": "WAIT_FOR_TERMINAL_PROVIDER_RECEIPT" if not failed else "BEM948-DISPATCH-AUTOREPAIR",
    }
    save(output, receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if failed:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
