#!/usr/bin/env python3
import http.client
import json
import os
from pathlib import Path
SEP = bytes.fromhex("0a").decode("ascii")
OUT = Path("governance/provider_gates/claude_primary_runtime_smoke_result.json")
REPORT = Path("governance/reports/claude_primary_runtime_smoke_result.md")
def truth(value):
    return bool(str(value or "").strip())
def main():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    model = os.environ.get("AUDITOR_MODEL", "") or os.environ.get("ANTHROPIC_MODEL", "") or "claude-3-5-haiku-20241022"
    result = {"schema_version":"claude_primary_runtime_smoke.v1","provider_checked":True,"primary_provider":"claude_api","has_anthropic_api_key":truth(key),"model":model,"status":"not_run","http_status":None,"claude_runtime_proven":False,"claude_authored_artifact":False,"blocker":None}
    if not truth(key):
        result["status"] = "missing_secret"
        result["blocker"] = {"code":"ANTHROPIC_API_KEY_MISSING","message":"Claude runtime smoke cannot run without secret."}
    else:
        body = json.dumps({"model": model, "max_tokens": 32, "messages": [{"role":"user","content":"Return exactly: CLAUDE_RUNTIME_SMOKE_OK"}]})
        headers = {"content-type":"application/json", "x-api-key": key, "anthropic-version":"2023-06-01"}
        try:
            conn = http.client.HTTPSConnection("api.anthropic.com", timeout=30)
            conn.request("POST", "/v1/messages", body=body, headers=headers)
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8", errors="ignore")
            result["http_status"] = resp.status
            if resp.status == 200:
                data = json.loads(raw)
                texts = []
                for item in data.get("content", []):
                    if isinstance(item, dict) and item.get("type") == "text":
                        texts.append(str(item.get("text", "")))
                text = " ".join(texts).strip()
                result["claude_text_preview"] = text[:80]
                result["claude_runtime_proven"] = "CLAUDE_RUNTIME_SMOKE_OK" in text
                result["claude_authored_artifact"] = result["claude_runtime_proven"]
                result["status"] = "runtime_proven" if result["claude_runtime_proven"] else "runtime_response_unexpected"
                result["blocker"] = None if result["claude_runtime_proven"] else {"code":"CLAUDE_RESPONSE_UNEXPECTED","message":"Claude returned 200 but did not return expected marker."}
            else:
                result["status"] = "http_not_ok"
                result["blocker"] = {"code":"CLAUDE_HTTP_NOT_OK","http_status":resp.status,"body_preview":raw[:300]}
        except:
            result["status"] = "runtime_error"
            result["blocker"] = {"code":"CLAUDE_RUNTIME_SMOKE_ERROR","message":"Runtime smoke raised an error."}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + SEP, encoding="utf-8")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("# Claude Primary Runtime Smoke Result" + SEP + SEP + "Status: " + str(result.get("status")) + SEP + "Runtime proven: " + str(result.get("claude_runtime_proven")) + SEP + "HTTP status: " + str(result.get("http_status")) + SEP + "Blocker: " + ("null" if result.get("blocker") is None else json.dumps(result.get("blocker"), ensure_ascii=False)) + SEP, encoding="utf-8")
    print(json.dumps({"status": result.get("status"), "runtime_proven": result.get("claude_runtime_proven")}, ensure_ascii=False))
if __name__ == "__main__":
    main()
