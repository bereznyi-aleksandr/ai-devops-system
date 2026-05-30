# BEM-895 autonomous next task selector
import json
from pathlib import Path
backlog = json.loads(Path("governance/autonomy/NEXT_EXECUTABLE_BACKLOG.json").read_text(encoding="utf-8"))
selected = None
for item in backlog.get("items", []):
    if item.get("status") == "pending":
        selected = item
        break
print(json.dumps({"selected": selected}, ensure_ascii=False, indent=2))
raise SystemExit(0)
