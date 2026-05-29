# BEM-883 registry validation tool
import json
from pathlib import Path
schemas = json.loads(Path("governance/state/registry_schemas.json").read_text(encoding="utf-8"))
errors = []
for name, spec in schemas.items():
    p = Path(spec["path"])
    if not p.exists():
        errors.append(f"{name}: missing file")
        continue
    data = json.loads(p.read_text(encoding="utf-8"))
    for field in spec["required"]:
        if field not in data:
            errors.append(f"{name}: missing {field}")
print("PASS" if not errors else "FAIL")
for err in errors:
    print(err)
raise SystemExit(0 if not errors else 1)
