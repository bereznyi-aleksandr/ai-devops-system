#!/usr/bin/env python3
import json
from pathlib import Path
SEP="\n"
STATE=Path("governance/state/curator_hourly_report_state.json")
DELIVERY=Path("governance/tmp/curator_hourly_report_delivery.txt")
RESPONSE=Path("governance/tmp/curator_hourly_report_response.json")
REPORT=Path("governance/reports/curator_hourly_report_runtime.md")

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}
state=load(STATE)
status=DELIVERY.read_text(encoding="utf-8", errors="ignore").strip() if DELIVERY.exists() else "not_sent_missing_delivery_file"
state["telegram_delivery"] = status
state["telegram_response_file"] = str(RESPONSE)
state["blocker"] = None if status == "sent" else {"code":"TELEGRAM_DELIVERY_NOT_SENT","status":status}
STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False)+SEP, encoding="utf-8")
with REPORT.open("a", encoding="utf-8") as handle:
    handle.write(SEP+"## Delivery"+SEP+status+SEP)
print(json.dumps({"telegram_delivery":status}, ensure_ascii=False))
