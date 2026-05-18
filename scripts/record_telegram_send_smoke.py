#!/usr/bin/env python3
import json
from pathlib import Path
SEP = bytes.fromhex("0a").decode("ascii")
STATUS = Path("governance/tmp/telegram_send_smoke_status.txt")
RESPONSE = Path("governance/tmp/telegram_send_smoke_response.json")
OUT = Path("governance/state/telegram_send_smoke_result.json")
REPORT = Path("governance/reports/telegram_send_smoke_result.md")
def read_text(path):
    return path.read_text(encoding="utf-8", errors="ignore").strip() if path.exists() else "missing"
def load_response():
    if not RESPONSE.exists():
        return {}
    try:
        return json.loads(RESPONSE.read_text(encoding="utf-8", errors="ignore"))
    except:
        return {"parse_error": True, "raw_preview": RESPONSE.read_text(encoding="utf-8", errors="ignore")[:300]}
status_text = read_text(STATUS)
resp = load_response()
http_status = None
telegram_ok = False
if status_text.startswith("sent_http_"):
    try:
        http_status = int(status_text.split("_")[-1])
    except:
        http_status = None
    telegram_ok = bool(isinstance(resp, dict) and resp.get("ok") is True)
elif status_text.startswith("not_sent_http_"):
    try:
        http_status = int(status_text.split("_")[-1])
    except:
        http_status = None
delivery = bool(http_status == 200 and telegram_ok)
blocker = None if delivery else {"code":"TELEGRAM_SEND_SMOKE_NOT_CONFIRMED", "status_text": status_text, "http_status": http_status, "telegram_response_preview": {"ok": resp.get("ok") if isinstance(resp, dict) else None, "description": resp.get("description") if isinstance(resp, dict) else None}}
result = {"schema_version":"telegram_send_smoke_result.v1", "status":"sent" if delivery else "not_confirmed", "status_text": status_text, "http_status": http_status, "telegram_ok": telegram_ok, "delivery_confirmed": delivery, "blocker": blocker}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + SEP, encoding="utf-8")
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text("# BEM-655 | Telegram Send Smoke Result" + SEP + SEP + "Status: " + result["status"] + SEP + "Delivery confirmed: " + str(delivery) + SEP + "HTTP status: " + str(http_status) + SEP + "Blocker: " + ("null" if blocker is None else json.dumps(blocker, ensure_ascii=False)) + SEP, encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
