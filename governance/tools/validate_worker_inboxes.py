# BEM-891 worker inbox delivery validator
import json
from pathlib import Path
queue = Path("governance/dispatch/dispatch_queue.jsonl")
errors = []
items = [json.loads(x) for x in queue.read_text(encoding="utf-8").splitlines() if x.strip()]
for item in items:
    contour = item.get("target_contour")
    inbox = Path("governance/worker/inbox") / contour / (item.get("dispatch_id") + ".json")
    if item.get("status") != "delivered":
        errors.append(f"{item.get('dispatch_id')}: not delivered")
    if not inbox.exists():
        errors.append(f"{item.get('dispatch_id')}: inbox file missing")
print("PASS" if not errors else "FAIL")
for err in errors:
    print(err)
raise SystemExit(0 if not errors else 1)
