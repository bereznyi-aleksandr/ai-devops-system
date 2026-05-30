# BEM-896 policy gate evaluator
import json
from pathlib import Path
policy = json.loads(Path("governance/state/policy_gate.json").read_text(encoding="utf-8"))
def evaluate(task):
    kind = task.get("kind")
    if kind in policy["operator_gate_required"]:
        return "GATE_OPERATOR"
    if kind in policy["allow_without_operator"]:
        return "ALLOW"
    return "GATE_OPERATOR"
samples = json.loads(Path("governance/policy/policy_gate_samples.json").read_text(encoding="utf-8"))
errors = []
for sample in samples:
    decision = evaluate(sample)
    print(sample["task_id"] + " -> " + decision)
    if decision != sample["expected"]:
        errors.append(sample["task_id"])
raise SystemExit(0 if not errors else 1)
