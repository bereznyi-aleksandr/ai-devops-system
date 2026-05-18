#!/usr/bin/env python3
import json
from pathlib import Path
SEP = bytes.fromhex("0a").decode("ascii")
STATE = Path("governance/state/curator_hourly_report_state.json")
OUT = Path("governance/state/curator_hourly_delivery_verification.json")
REPORT = Path("governance/reports/curator_hourly_delivery_verification.md")
def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except:
        return {}
data = load_json(STATE)
delivery = data.get("telegram_delivery")
ok = delivery == "sent"
result = {"schema_version":"curator_hourly_delivery_verification.v1","checked":True,"telegram_delivery":delivery,"delivery_confirmed":ok,"status":"pass" if ok else "not_confirmed","blocker":None if ok else {"code":"TELEGRAM_DELIVERY_NOT_CONFIRMED","delivery":delivery}}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + SEP, encoding="utf-8")
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text("# Curator Hourly Delivery Verification" + SEP + SEP + "Status: " + result["status"] + SEP + "Telegram delivery: " + str(delivery) + SEP + "Blocker: " + ("null" if result.get("blocker") is None else json.dumps(result.get("blocker"), ensure_ascii=False)) + SEP, encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
