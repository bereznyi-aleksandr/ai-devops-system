# BEM-887 product repository registration validator
import json
from pathlib import Path
schema = json.loads(Path("governance/state/product_repository_registration_schema.json").read_text(encoding="utf-8"))
registry = json.loads(Path("governance/state/product_repository_registry.json").read_text(encoding="utf-8"))
errors = []
for repo in registry.get("repositories", []):
    for field in schema["required"]:
        if field not in repo:
            errors.append(f"{repo.get('repository_id','unknown')}: missing {field}")
print("PASS" if not errors else "FAIL")
for err in errors:
    print(err)
raise SystemExit(0 if not errors else 1)
