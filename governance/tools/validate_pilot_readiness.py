# BEM-901 pilot readiness validator
import json
from pathlib import Path
state = json.loads(Path("governance/state/pilot_readiness.json").read_text(encoding="utf-8"))
errors = []
for name, folder in state.get("folders", {}).items():
    if not Path(folder).exists():
        errors.append(f"missing folder {name}: {folder}")
print("PASS" if not errors else "FAIL")
for err in errors:
    print(err)
raise SystemExit(0 if not errors else 1)
