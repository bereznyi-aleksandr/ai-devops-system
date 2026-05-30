# BEM-903 product onboarding validator
import json
from pathlib import Path
sample = json.loads(Path("governance/pilot/product_onboarding/synthetic_product_registration.json").read_text(encoding="utf-8"))
required = ["repository_id","repository_name","owner_object","worker_object","purpose","feedback_route"]
errors = []
for field in required:
    if field not in sample or not str(sample.get(field, "")).strip():
        errors.append("missing " + field)
print("PASS" if not errors else "FAIL")
for err in errors:
    print(err)
raise SystemExit(0 if not errors else 1)
