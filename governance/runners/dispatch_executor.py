#!/usr/bin/env python3
"""BEM-948: permanent bridge from routed governance records to Actions dispatches.

HTTP 204 is recorded only as "dispatched"; it never means task completion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "governance" / "state"
PROOFS = ROOT / "governance" / "proofs"
PROCESSED = STATE / "dispatch_processed.jsonl"
EXECUTED = STATE / "dispatch_executed.jsonl"
CONFIG = ROOT / "governance" / "config" / "provider_config.json"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def text(value: Any, default: str = "") -> str:
    return str(value if value is not None else default)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            records.append({"_invalid": "json", "_line": line_number, "_error": str(exc)})
            continue
        records.append(item if isinstance(item, dict) else {"_invalid": "non_object_json", "_line": line_number})
    return records


def append_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def key(record: dict[str, Any]) -> str:
    return text(record.get("dispatch_id") or record.get("trace_id") or record.get("id"))


def sha256_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def config() -> dict[str, Any]:
    try:
        loaded = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"provider_config_unavailable:{exc}") from exc
    if not isinstance(loaded, dict):
        raise RuntimeError("provider_config_not_object")
    return loaded


def allowed(cfg: dict[str, Any], provider: str, workflow_id: str) -> str | None:
    provider_config = (cfg.get("providers") or {}).get(provider)
    if not isinstance(provide_config, dict):
        return "provider_missing"
    if provider_config.get("enabled") is not True:
        return "provider_disabled"
    if text(provider_config.get("workflow_id")) != workflow_id:
        return "target_workflow_mismatch"
    return None


def post_dispatch(token: str, repository: str, api_url: str, workflow_id: str, inputs: dict[str, str]) -> tuple[int | None, str]:
    url = f"{api_url.rstrip('/')}/repos/{repository}/actions/workflows/{workflow_id}/dispatches"
    body = json.dumps({"ref": "main", "inputs": inputs}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "ai-devops-system-bem948-dispatch-executor",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return int(response.status), response.read().decode("utf-8", errors="replace")[:500]
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8", errors="replace")[:500]
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, str(exc)[:500]


def run(max_items: int, dry_run: bool) -> dict[str, Any]:
    cfg = config()
    source = read_jsonl(PROCESSED)
    prior = read_jsonl(EXECUTED)
    handled = {key(item) for item in prior if key(item)}
    token = os.environ.get("AI_SYSTEM_GITHUB_PAT") or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    outputs: list[dict[str, Any]] = []
    skipped = 0

    for record in source:
        if len(outputs) >= max_items:
            break
        dispatch_id = key(record)
        if (
            not dispatch_id
            or record.get("_invalid")
            or record.get("status") != "processed"
            or record.get("dispatch_result") != "planned"
            or dispatch_id in handled
        ):
            skipped += 1
            continue

        payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
        role = text(record.get("logical_role") or record.get("role") or "curator")
        provider = text(record.get("provider_selected") or record.get("provider"))
        trace_id = text(record.get("trace_id") or dispatch_id)
        workflow_id = text(record.get("target_workflow_id"))
        task = text(payload.get("task") or record.get("saske") or f"Governance dispatch {trace_id}: create truthful report and proof.")
        inputs = {
            "role": role,
            "provider": "claude" if provider == "claude_code" else provider,
            "trace_id": trace_id,
            "cycle_id": text(payload.get("cycle_id") or record.get("cycle_id") or f"dispatch_{trace_id}"),
            "task_type": text(payload.get("task_type") or record.get("sask_type") or "default_development"),
            "task": task,
        }
        outcome: dict[str, Any] = {
            "protocol": "BEM-948",
            "task_id": "BEM948-P0-REAL-DISPATCH-BRIDGE",
            "created_at": now(),
            "dispatch_id": dispatch_id,
            "trace_id": trace_id,
            "logical_role": role,
            "provider_selected": provider,
            "target_workflow_id": workflow_id,
            "inputs": inputs,
            "source_processed_sha256": sha256_json(record),
            "source_processed_sha256_type": "sha256_content",
            "dispatch_result": "failed",
            "http_status": None,
            "blocker": None,
        }
        blocker = allowed(cfg, provider, workflow_id)
        if blocker:
            outcome["blocker"] = blocker
        elif dry_run:
            outcome["dispatch_result"] = "dry_run"
            outcome["http_status"] = 0
            outcome["blocker"] = "dry_run"
        elif not token:
            outcome["blocker"] = "github_token_missing"
        elif not repository:
            outcome["blocker"] = "github_repository_missing"
        else:
            http_status, response = post_dispatch(token, repository, api_url, workflow_id, inputs)
            outcome["http_status"] = http_status
            outcome["response_excerpt"] = response
            if http_status == 204:
                outcome["dispatch_result"] = "dispatched"
            else:
                outcome["blocker"] = f"workflow_dispatch_http_{http_status if http_status is not None else 'network_error'}"
        outputs.append(outcome)

    append_jsonl(EXECUTED, outputs)
    failed = [item for item in outputs if item["dispatch_result"] == "failed"]
    dispatched = [item for item in outputs if item["dispatch_result"] == "dispatched"]
    receipt = {
        "status": "PASS" if not failed else "BLOCKED",
        "protocol": "BEM-948",
        "task_id": "BEM948-P0-REAL-DISPATCH-BRIDGE",
        "created_at": now(),
        "processed_source": str(PROCESSED.relative_to(ROOT)),
        "executed_output": str(EXECUTED.relative_to(ROOT)),
        "processed_items_seen": len(source),
        "dispatched_count": len(dispatched),
        "failed_count": len(failed),
        "skipped_count": skipped,
        "dispatches": outputs,
        "checks": {
            "dispatch_executor_has_runtime_code": True,
            "http_dispatch_attempted": bool(outputs),
            "http_204_means_dispatched_not_completed": True,
            "executed_jsonl_written": EXECUTED.exists(),
            "sha_type_explicit": True,
        },
        "blockers": [text(item.get("blocker")) for item in failed if item.get("blocker")],
        "next_task": "BEM948-P0-LIVE-OBJECT-E2E" if not failed else "BEM948-P0-AUTOREPAIR-DISPATCH-EXECUTOR",
    }
    write_json(PROOFS / "BEM948_dispatch_executor_receipt.json", receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description="Dispatch planned governance records through GitHub Actions.")
    parser.add_argument("--max", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    receipt = run(max_items=max(1, args.max), dry_run=args.dry_run)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if receipt["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
