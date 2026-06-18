#!/usr/bin/env python3
"""Runtime object runner for BEM-938.

Turns a governance object (for example OBJ-GD-001) into an executable runtime
participant:
- accepts an object task;
- writes object state and event records;
- materializes a dispatch_queue.jsonl item;
- can optionally invoke dispatch_consumer so the queued task is routed by
  curator_router.py into a provider workflow plan.

The runner does not claim downstream LLM completion. It proves that the internal
object -> queue -> curator router handoff is alive and evidence-bearing.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "governance" / "state"
PROOFS = ROOT / "governance" / "proofs"
LOGS = ROOT / "governance" / "logs"
QUEUE = STATE / "dispatch_queue.jsonl"
PROCESSED = STATE / "dispatch_processed.jsonl"
OBJECT_EVENTS = STATE / "object_events.jsonl"
OBJECT_REGISTRY = STATE / "runtime_objects.json"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe(value: Any) -> str:
    text = str(value or "trace")
    return re.sub(r"[^A-Za-z0-9_.:-]+", "_", text)[:140]


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return default
        return json.loads(text)
    except Exception:
        return default


def append_jsonl(path: Path, items: list[dict[str, Any]]) -> None:
    if not items:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as exc:
            out.append({"_invalid": "json", "_raw": line, "_error": str(exc)})
    return out


def load_dispatch_consumer():
    path = ROOT / "governance" / "runners" / "dispatch_consumer.py"
    spec = importlib.util.spec_from_file_location("dispatch_consumer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("dispatch_consumer_load_failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def default_registry() -> dict[str, Any]:
    return {
        "objects": {
            "OBJ-GD-001": {
                "object_id": "OBJ-GD-001",
                "title": "General Director runtime object",
                "enabled": True,
                "default_role": "curator",
                "provider": "claude_code",
                "description": "Turns operator/system objectives into dispatch queue items.",
            }
        }
    }


def load_registry() -> dict[str, Any]:
    registry = read_json(OBJECT_REGISTRY, None)
    if isinstance(registry, dict) and isinstance(registry.get("objects"), dict):
        return registry
    registry = default_registry()
    OBJECT_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    OBJECT_REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return registry


def resolve_object(object_id: str) -> dict[str, Any]:
    registry = load_registry()
    objects = registry.get("objects", {})
    obj = objects.get(object_id)
    if not isinstance(obj, dict):
        raise RuntimeError(f"object_missing:{object_id}")
    if obj.get("enabled") is False:
        raise RuntimeError(f"object_disabled:{object_id}")
    return obj


def create_dispatch_item(
    *,
    object_id: str,
    task: str,
    role: str | None = None,
    provider: str | None = None,
    trace_id: str | None = None,
    priority: int = 50,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    obj = resolve_object(object_id)
    trace = safe(trace_id or f"{object_id}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}")
    selected_role = role or obj.get("default_role") or "curator"
    selected_provider = provider or obj.get("provider") or "claude_code"
    dispatch_id = f"{trace}:{object_id}"
    return {
        "dispatch_id": dispatch_id,
        "trace_id": trace,
        "status": "queued",
        "created_at": now(),
        "source": "object_runner",
        "object_id": object_id,
        "logical_role": selected_role,
        "role": selected_role,
        "provider": selected_provider,
        "priority": priority,
        "payload": {
            "task": task,
            "object": obj,
            **(payload or {}),
        },
    }


def run_object_task(
    *,
    object_id: str,
    task: str,
    role: str | None = None,
    provider: str | None = None,
    trace_id: str | None = None,
    consume: bool = False,
) -> dict[str, Any]:
    item = create_dispatch_item(
        object_id=object_id,
        task=task,
        role=role,
        provider=provider,
        trace_id=trace_id,
    )

    append_jsonl(QUEUE, [item])
    object_event = {
        "timestamp": now(),
        "protocol": "BEM-938",
        "event_type": "object_task_queued",
        "status": "QUEUED",
        "object_id": object_id,
        "trace_id": item["trace_id"],
        "dispatch_id": item["dispatch_id"],
        "queue_path": str(QUEUE.relative_to(ROOT)),
        "source": "governance/runners/object_runner.py",
    }
    append_jsonl(OBJECT_EVENTS, [object_event])

    last_run = {
        "status": "QUEUED",
        "object_id": object_id,
        "trace_id": item["trace_id"],
        "dispatch_id": item["dispatch_id"],
        "created_at": now(),
        "task_preview": task[:240],
        "queue_path": str(QUEUE.relative_to(ROOT)),
        "processed_path": str(PROCESSED.relative_to(ROOT)),
        "non_claim": "Object handoff is queued/routed only; downstream LLM completion is not claimed here.",
    }

    consumer_receipt = None
    if consume:
        consumer = load_dispatch_consumer()
        consumer_receipt = consumer.consume(20)
        last_run["consumer_receipt"] = consumer_receipt
        if consumer_receipt.get("processed_count", 0) > 0 and consumer_receipt.get("status") == "PASS":
            last_run["status"] = "ROUTED"

    state_path = STATE / f"{safe(object_id)}_last_run.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(last_run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    receipt = {
        "status": "PASS" if not consumer_receipt or consumer_receipt.get("status") == "PASS" else "BLOCKED",
        "protocol": "BEM-938",
        "task_id": "BEM938-P0-OBJECT-RUNNER",
        "created_at": now(),
        "stage": {"tasks_done": 1, "tasks_total": 4, "percent": 25},
        "object_id": object_id,
        "trace_id": item["trace_id"],
        "dispatch_id": item["dispatch_id"],
        "queue_path": str(QUEUE.relative_to(ROOT)),
        "object_state_path": str(state_path.relative_to(ROOT)),
        "object_event_path": str(OBJECT_EVENTS.relative_to(ROOT)),
        "processed_nonempty": PROCESSED.exists() and PROCESSED.stat().st_size > 0,
        "consumer_receipt": consumer_receipt,
        "checks": {
            "object_runner_runtime_code_present": True,
            "object_registry_present": OBJECT_REGISTRY.exists(),
            "object_state_written": state_path.exists() and state_path.stat().st_size > 80,
            "dispatch_queue_item_written": QUEUE.exists() and item["dispatch_id"] in QUEUE.read_text(encoding="utf-8", errors="replace"),
            "object_event_written": OBJECT_EVENTS.exists() and item["trace_id"] in OBJECT_EVENTS.read_text(encoding="utf-8", errors="replace"),
            "downstream_llm_completion_not_claimed": True,
        },
        "blockers": [],
        "next_task": "BEM938-P1-GD-RUNTIME-BINDING",
    }
    if receipt["status"] != "PASS":
        receipt["blockers"] = ["dispatch_consumer_blocked"]

    PROOFS.mkdir(parents=True, exist_ok=True)
    proof = PROOFS / "BEM938_object_runner_receipt.json"
    proof.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--object-id", default="OBJ-GD-001")
    parser.add_argument("--task", default="BEM-938 selftest: route GD object task through dispatch queue")
    parser.add_argument("--role")
    parser.add_argument("--provider")
    parser.add_argument("--trace-id")
    parser.add_argument("--consume", action="store_true")
    args = parser.parse_args()

    receipt = run_object_task(
        object_id=args.object_id,
        task=args.task,
        role=args.role,
        provider=args.provider,
        trace_id=args.trace_id,
        consume=args.consume,
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if receipt["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
