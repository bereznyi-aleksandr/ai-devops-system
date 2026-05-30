#!/usr/bin/env python3
# Deterministic dispatch consumer for governance dispatch_queue.jsonl.
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "governance/dispatch/dispatch_queue.jsonl"
POLICY = ROOT / "governance/state/policy_gate.json"
STATE = ROOT / "governance/state/dispatch_consumer_state.json"
REPORT = ROOT / "governance/reports/dispatch_consumer_last_run.json"
VALID_CONTOURS = {"WRK-C1", "WRK-C2", "WRK-C3"}

def load_json(path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default

def decision_for(item, policy):
    kind = item.get("kind", "routine_development")
    if kind in policy.get("operator_gate_required", []):
        return "GATE_OPERATOR"
    if kind in policy.get("allow_without_operator", []):
        return "ALLOW"
    return "ALLOW" if item.get("task_id") and item.get("target_contour") in VALID_CONTOURS else "GATE_OPERATOR"

def main():
    policy = load_json(POLICY, {"operator_gate_required": [], "allow_without_operator": ["routine_development"]})
    items = []
    if QUEUE.exists():
        items = [json.loads(line) for line in QUEUE.read_text(encoding="utf-8").splitlines() if line.strip()]
    processed, gated, errors = [], [], []
    for item in items:
        if item.get("status") != "queued":
            continue
        contour = item.get("target_contour")
        if contour not in VALID_CONTOURS:
            item["status"] = "failed"
            item["error"] = "invalid target contour"
            errors.append(item.get("dispatch_id", "unknown"))
            continue
        decision = decision_for(item, policy)
        if decision == "GATE_OPERATOR":
            item["status"] = "operator_gate"
            item["gate_reason"] = "policy_gate_required"
            gated.append(item.get("dispatch_id"))
            continue
        inbox_dir = ROOT / "governance/worker/inbox" / contour
        inbox_dir.mkdir(parents=True, exist_ok=True)
        inbox_file = inbox_dir / (item.get("dispatch_id", "dispatch") + ".json")
        item["status"] = "delivered"
        item["consumer"] = "dispatch_consumer.py"
        item["inbox_ref"] = str(inbox_file.relative_to(ROOT))
        inbox_file.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
        processed.append(item.get("dispatch_id"))
    QUEUE.write_text("\n".join(json.dumps(i, ensure_ascii=False) for i in items) + ("\n" if items else ""), encoding="utf-8")
    result = {"status": "PASS" if not errors else "FAIL", "processed": processed, "gated": gated, "errors": errors}
    STATE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1

if __name__ == "__main__":
    raise SystemExit(main())
