#!/usr/bin/env python3
"""BEM-948 permanent bridge: planned governance record -> Actions dispatch.

HTTP 204 is recorded as `dispatched`, never as `completed`.
"""
import argparse
import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[2]
STATE = root / "governance" / "state"
PROCESSED = STATE / "dispatch_processed.jsonl"
EXECUTED = STATE / "dispatch_executed.jsonl"
PROOF = root / "governance" / "proofs" / "BEM948_dispatch_executor_receipt.json"
CONFIG = root / "governance" / "config" / "provider_config.json"


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rows(path):
    if not path.exists():
        return []
    out = []
    for number, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
            out.append(value if isinstance(value, dict) else {"_invalid": "non_object", "_line": number})
        except json.JSONDecodeError as exc:
            out.append({"_invalid": "json", "_line": number, "_error": str(exc)})
    return out


def append(path, values):
    if not values:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def key(item):
    return str(item.get("dispatch_id") or item.get("trace_id") or item.get("id") or "")


def post(token, repo, api, workflow, inputs):
    url = f"{api.rstrip('/')}/repos/{repo}/actions/workflows/{workflow}/dispatches"
    body = json.dumps({"ref": "main", "inputs": inputs}, ensure_ascii=False).encode()
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "ai-devops-system-bem948-dispatch-executor",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return int(response.status), response.read().decode("utf-8", errors="replace")[:500]
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8", errors="replace")[:500]
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return None, str(exc)[:500]


def run(maximum, trace_filter=None, dry_run=False):
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    prior = {key(item) for item in rows(EXECUTED) if key(item)}
    token = os.getenv("AI_SYSTEM_GITHUB_PAT") or os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or ""
    repo = os.getenv("GITHUB_REPOSITORY", "")
    api = os.getenv("GITHUB_API_URL", "https://api.github.com")
    out, skipped = [], 0

    for item in rows(PROCESSED):
        if len(out) >= maximum:
            break
        dispatch_id = key(item)
        trace_id = str(item.get("trace_id") or dispatch_id)
        eligible = (
            dispatch_id and not item.get("_invalid")
            and item.get("status") == "processed"
            and item.get("dispatch_result") == "planned"
            and dispatch_id not in prior
            and (not trace_filter or trace_id == trace_filter)
        )
        if not eligible:
            skipped += 1
            continue

        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        role = str(item.get("logical_role") or item.get("role") or "curator")
        provider = str(item.get("provider_selected") or item.get("provider") or "")
        workflow = str(item.get("target_workflow_id") or "")
        config = (cfg.get("providers") or {}).get(provider, {})
        inputs = {
            "role": role,
            "provider": "claude" if provider == "claude_code" else provider,
            "trace_id": trace_id,
            "cycle_id": str(payload.get("cycle_id") or item.get("cycle_id") or f"dispatch_{trace_id}"),
            "task_type": str(payload.get("task_type") or "default_development"),
            "task": str(payload.get("task") or f"Governance dispatch {trace_id}"),
        }
        source_hash = hashlib.sha256(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        record = {
            "protocol": "BEM-948",
            "task_id": "BEM948-P0-REAL-DISPATCH-BRIDGE",
            "created_at": now(),
            "dispatch_id": dispatch_id,
            "trace_id": trace_id,
            "logical_role": role,
            "provider_selected": provider,
            "target_workflow_id": workflow,
            "inputs": inputs,
            "source_processed_sha256": source_hash,
            "source_processed_sha256_type": "sha256_content",
            "dispatch_result": "failed",
            "http_status": None,
            "blocker": None,
        }
        if not config:
            record["blocker"] = "provider_missing"
        elif config.get("enabled") is not True:
            record["blocker"] = "provider_disabled"
        elif config.get("workflow_id") != workflow:
            record["blocker"] = "target_workflow_mismatch"
        elif dry_run:
            record.update(dispatch_result="dry_run", http_status=0, blocker="dry_run")
        elif not token:
            record["blocker"] = "github_token_missing"
        elif not repo:
            record["blocker"] = "github_repository_missing"
        else:
            status, response = post(token, repo, api, workflow, inputs)
            record.update(http_status=status, response_excerpt=response)
            if status == 204:
                record["dispatch_result"] = "dispatched"
            else:
                record["blocker"] = f"workflow_dispatch_http_{status if status is not None else 'network_error'}"
        out.append(record)

    append(EXECUTED, out)
    failures = [item for item in out if item["dispatch_result"] == "failed"]
    no_match = bool(trace_filter) and not out
    receipt = {
        "status": "PASS" if not failures and not no_match else "BLOCKED",
        "protocol": "BEM-948",
        "task_id": "BEM948-P0-REAL-DISPATCH-BRIDGE",
        "created_at": now(),
        "processed_source": "governance/state/dispatch_processed.jsonl",
        "executed_output": "governance/state/dispatch_executed.jsonl",
        "trace_filter": trace_filter,
        "dispatched_count": sum(x["dispatch_result"] == "dispatched" for x in out),
        "failed_count": len(failures),
        "skipped_count": skipped,
        "dispatches": out,
        "checks": {
            "dispatch_executor_has_runtime_code": True,
            "http_dispatch_attempted": bool(out),
            "http_204_means_dispatched_not_completed": True,
            "trace_scope_enforced": bool(trace_filter),
            "sha_type_explicit": True,
        },
        "blockers": [x["blocker"] for x in failures if x.get("blocker")]
        + (["corresponding_processed_dispatch_not_found"] if no_match else []),
        "next_task": "BEM948-P0-LIVE-OBJECT-E2E" if not failures and not no_match else "BEM948-P0-AUTOREPAIR-DISPATCH-EXECUTOR",
    }
    write(PROOF, receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=20)
    parser.add_argument("--trace-id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    receipt = run(max(1, args.max), args.trace_id, args.dry_run)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if receipt["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
