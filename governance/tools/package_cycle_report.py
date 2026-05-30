# BEM-897 cycle report packager
import json
from pathlib import Path
cycle_id = "CYCLE-BEM897-001"
package = json.loads(Path("governance/cycles/" + cycle_id + ".json").read_text(encoding="utf-8"))
missing = [p for p in package.get("proofs", []) if not Path(p).exists()]
print("PASS" if not missing else "FAIL")
for p in missing:
    print("missing " + p)
raise SystemExit(0 if not missing else 1)
