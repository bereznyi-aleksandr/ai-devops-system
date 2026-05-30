# BEM-892 contour processing validator
import json
from pathlib import Path
errors = []
for contour in ["WRK-C1","WRK-C2","WRK-C3"]:
    results = list((Path("governance/worker/results") / contour).glob("RES-*.json"))
    if not results:
        errors.append(f"{contour}: result missing")
queue = Path("governance/dispatch/dispatch_queue.jsonl")
if queue.exists():
    for item in [json.loads(x) for x in queue.read_text(encoding="utf-8").splitlines() if x.strip()]:
        if item.get("status") != "completed":
            errors.append(f"{item.get('dispatch_id')}: not completed")
print("PASS" if not errors else "FAIL")
for err in errors:
    print(err)
raise SystemExit(0 if not errors else 1)
