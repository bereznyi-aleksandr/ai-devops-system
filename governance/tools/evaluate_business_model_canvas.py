# BEM-902 Business Model Canvas evaluator
import json
from pathlib import Path
blocks = ["customer_segments","value_proposition","channels","customer_relationships","revenue_streams","key_resources","key_activities","key_partnerships","cost_structure"]
def evaluate(path):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    errors = []
    for block in blocks:
        if block not in doc.get("blocks", {}):
            errors.append("missing block " + block)
        elif doc["blocks"][block].get("required") and not str(doc["blocks"][block].get("value", "")).strip():
            errors.append("empty block " + block)
    return errors
errors = evaluate("governance/pilot/canvas/business_model_canvas_synthetic_example.json")
print("PASS" if not errors else "FAIL")
for err in errors:
    print(err)
raise SystemExit(0 if not errors else 1)
