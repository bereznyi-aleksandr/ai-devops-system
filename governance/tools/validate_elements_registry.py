# BEM-920 elements registry validator
import json
from pathlib import Path
registry = json.loads(Path("governance/state/elements_registry.json").read_text(encoding="utf-8"))
objects = json.loads(Path("governance/state/objects_registry.json").read_text(encoding="utf-8"))
errors = []
ids = set()
for el in registry.get("elements", []):
    for field in registry.get("required_fields", []):
        if field not in el:
            errors.append(f"{el.get('id','unknown')} missing {field}")
    if el.get("id") in ids:
        errors.append("duplicate element id " + el.get("id"))
    ids.add(el.get("id"))
    if el.get("prompt_ref") and not Path(el["prompt_ref"]).exists():
        errors.append(f"{el.get('id')} prompt missing {el.get('prompt_ref')}")
for obj in objects.get("objects", []):
    for eid in obj.get("elements", []):
        if eid not in ids:
            errors.append("object element not registered: " + eid)
print("PASS" if not errors else "FAIL")
for err in errors:
    print(err)
raise SystemExit(0 if not errors else 1)
