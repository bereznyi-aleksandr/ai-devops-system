\
#!/usr/bin/env python3
"""BEM-948 permanent object-to-dispatch adapter with explicit task type.

This adapter preserves the existing object_runner -> dispatch_consumer route while
making the downstream workflow task_type explicit. It does not execute an LLM itself and it never treats an HTTP dispatch as completed work.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROOFS = ROOT / "governance" / "proofs"


def load_object_runner() -> Any:
    path = ROOT / "governance" / "runners" / "object_runner.py"
    spec = importlib.util.spec_from_file_location("bem948_object_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("object_runner_load_failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Queue and route one trace-bound object task with an explicit workflow tasktype."
    )
    parser.add_argument("--object-id", default="OBJ-GD-001")
    parser.add_argument("--task", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--task-type", required=True)
    parser.add_argument("--consume", action="store_true")
    args = parser.parse_args()

    trace_id = args.trace_id.strip()
    task_type = args.task_type.strip()
    if not trace_id:
        raise SystemExit("trace_id_required")
    if not task_type:
        raise SystemExit("task_type_required")

    runner = load_object_runner()
    item = runner.create_dispatch_item(
        object_id=args.object_id,
        task=args.task,
        role=args.role,
        provider=args.provider,
        trace_id=trace_id,
        payload={"task_type": task_type, "bem948_task_type_explicit": True},
    )
    runner.append_jsonl(runner.QUEUE, [item])

    event = {
        "timestamp": runner.now(),
        "protocol": "BEM-948",
        "event_type": "object_task_queued_with_explicit_task_type",
        "status": "QUEUED",
        "object_id": args.object_id,
        "trace_id": trace_id,
        "dispatch_id": item["dispatch_id"],
        "task_type": task_type,
        "source": "governance/runners/object_dispatch_bridge.py",
    }
    runner.append_jsonl(runner.OBJECT_EVENTS, [event])

    consumer_receipt = None
    routed = False
    if args.consume:
        consumer = runner.load_dispatch_consumer()
        consumer_receipt = consumer.consume(20)
        routed = (
            consumer_receipt.get("status") == "PASS"
            and consumer_receipt.get("processed_count", 0) > 0
        )

    state_path = runner.STATE / f"{runner.safe(args.object_id)}_last_run.json"
    state = {
        "status": "ROUTED" if routed else "QUEUED",
        "protocol": "BEM-948",
        "object_id": args.object_id,
        "trace_id": trace_id,
        "dispatch_id": item["dispatch_id"],
        "task_type": task_type,
        "created_at": runner.now(),
        "queue_path": str(runner.QUEUE.relative_to(runner.ROOT)),
        "processed_path": str(runner.PROCESSED.relative_to(runner.ROOT)),
        "consumer_receipt": consumer_receipt,
        "non_claim": (
            "This adapter proves queue/route only. A downstream HTTP 204 is dispatch, "
            "not executed/completed work."
        ),
    }
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    PROOFS.mkdir(parents=True, exist_ok=True)
    receipt = {
        "status": "PASS" if routed else "BLOCKED",
        "protocol": "BEM-948",
        "task_id": "BEM948-P0-OBJECT-DISPATCH-BRIDGE",
        "created_at": runner.now(),
        "object_id": args.object_id,
        "trace_id": trace_id,
        "dispatch_id": item["dispatch_id"],
        "task_type": task_type,
        "queue_path": str(runner.QUEUE.relative_to(runner.ROOT)),
        "processed_path": str(runner.PROCESSED.relative_to(runner.ROOT)),
        "object_state_path": str(state_path.relative_to(runner.ROOT)),
        "consumer_receipt": consumer_receipt,
        "checks": {
            "trace_id_required": True,
            "task_type_required": True,
            "object_runner_runtime_reused": True,
            "dispatch_consumer_runtime_reused": bool(args.consume),
            "downstream_llm_completion_not_claimed": True,
            "sha_type_explicit": True,
        },
        "blockers": [] if routed else ["dispatch_consumer_did_not_route_trace"],
        "next_task": (
            "BEM948-P0-REAL-DISPATCH-BRIDGE"
            if routed else "BEM948-P0-AUTOREPAIR-OBJECT-DISPATCH-BRIDGE"
        ),
    }
    (PROOFS / "BEM948_object_dispatch_bridge_receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if receipt["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
