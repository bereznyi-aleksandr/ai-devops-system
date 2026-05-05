#!/usr/bin/env python3
"""Forced proof for E4-002 role FSM step-limit.

This script exercises the real role_orchestrator.register_role_step path by
creating a synthetic active cycle at max_role_steps_per_cycle and then adding
one more role_result step. Expected result: step_limit_exceeded.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import role_orchestrator as ro  # noqa: E402


def main() -> int:
    trace_id = os.environ.get("TRACE_ID", "proof_e4_002_step_limit_forced")
    cycle_id = os.environ.get("CYCLE_ID", "cyc_e4_002_step_limit_forced")

    seq_policy = ro.load_json(ro.SEQUENCE_PATH, {})
    controls = ro.cycle_controls(seq_policy)
    max_steps = controls["max_role_steps_per_cycle"]

    state = ro.load_json(ro.STATE_PATH, {"version": 1, "cycles": {}})
    cycles = state.setdefault("cycles", {})

    history = []
    for idx in range(1, max_steps + 1):
        history.append({
            "step": idx,
            "type": "role_dispatch" if idx % 2 else "role_result",
            "role": "auditor" if idx % 2 else "executor",
            "provider": "gpt",
            "timestamp": ro.now_iso(),
            "proof_seed": True,
        })

    cycle = {
        "cycle_id": cycle_id,
        "trace_id": trace_id,
        "task_type": "architecture_change",
        "sequence": ["analyst", "auditor", "executor", "auditor", "curator_summary"],
        "current_index": 3,
        "current_role": "auditor",
        "current_provider": "gpt",
        "status": "role_dispatched",
        "task": "E4-002 forced proof: exceed max_role_steps_per_cycle without dispatching another role.",
        "step_count": max_steps,
        "step_history": history,
        "updated_at": ro.now_iso(),
        "proof_type": "forced_step_limit",
    }
    cycles[cycle_id] = cycle
    state["updated_at"] = ro.now_iso()
    state["last_cycle_id"] = cycle_id
    state["last_trace_id"] = trace_id
    state["status"] = "cycle_started"

    ro.register_role_step(
        state,
        cycle_id,
        cycle,
        "role_result",
        "auditor",
        "gpt",
        post_report=True,
    )

    final_state = ro.load_json(ro.STATE_PATH, {})
    final_cycle = final_state.get("cycles", {}).get(cycle_id, {})
    ok = final_cycle.get("status") == "step_limit_exceeded"
    print("BEM-E4-002 | STEP LIMIT FORCED PROOF")
    print(f"CYCLE_ID={cycle_id}")
    print(f"TRACE_ID={trace_id}")
    print(f"MAX_STEPS={max_steps}")
    print(f"FINAL_STATUS={final_cycle.get('status')}")
    print(f"STEP_COUNT={final_cycle.get('step_count')}")
    print("RESULT=" + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
