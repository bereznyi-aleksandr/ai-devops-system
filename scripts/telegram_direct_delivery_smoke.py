#!/usr/bin/env python3
import http.client
import json
import os
from pathlib import Path
SEP = bytes.fromhex("0a").decode("ascii")
OUT = Path("governance/state/telegram_direct_delivery_smoke.json")
REPORT = Path("governance/reports/telegram_direct_delivery_smoke.md")
def present(v):
    return bool(str(v or "").strip())
def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    text = "BEM-635 | TELEGRAM DIRECT DELIVERY SMOKE | Канал доставки проверяется автономно"
    result = {"schema_version":"telegram_direct_delivery_smoke.v1","status":"not_run","has_token":present(token),"has_chat_id":present(chat_id),"http_status":None,"delivery_confirmed":False,"blocker":None}
    if not present(token) or not present(chat_id):
        result["status"] = "missing_secret"
        result["blocker"] = {"code":"TELEGRAM_SECRET_MISSING","has_token":present(token),"has_chat_id":present(chat_id)}
    else:
        try:
            params = "chat_id=" + chat_id + "&disable_web_page_preview=true&text=" + text.replace(" ", "%20").replace("|", "%7C")
            conn = http.client.HTTPSConnection("api.telegram.org", timeout=30)
            conn.request("POST", "/bot" + token + "/sendMessage", body=params, headers={"content-type":"application/x-www-form-urlencoded"})
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8", errors="ignore")
            result["http_status"] = resp.status
            result["response_preview"] = raw[:300]
            if resp.status == 200 and "ok" in raw:
                result["status"] = "sent"
                result["delivery_confirmed"] = True
            else:
                result["status"] = "http_not_ok"
                result["blocker"] = {"code":"TELEGRAM_HTTP_NOT_OK","http_status":resp.status,"response_preview":raw[:300]}
        except:
            result["status"] = "runtime_error"
            result["blocker"] = {"code":"TELEGRAM_SMOKE_RUNTIME_ERROR"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + SEP, encoding="utf-8")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("# Telegram Direct Delivery Smoke" + SEP + SEP + "Status: " + result["status"] + SEP + "Delivery confirmed: " + str(result["delivery_confirmed"]) + SEP + "HTTP status: " + str(result.get("http_status")) + SEP + "Blocker: " + ("null" if result.get("blocker") is None else json.dumps(result.get("blocker"), ensure_ascii=False)) + SEP, encoding="utf-8")
    print(json.dumps({"status": result["status"], "delivery_confirmed": result["delivery_confirmed"]}, ensure_ascii=False))
if __name__ == "__main__":
    main()
