#!/usr/bin/env python3
import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
PASTEBOX = ROOT / "governance/state/gpt_relay_pastebox.txt"
INBOX = ROOT / "governance/state/gpt_relay_inbox"
HISTORY = ROOT / "governance/state/gpt_relay_pastebox_history"
EVENTS = ROOT / "governance/events/gpt_relay_ingress_bridge.jsonl"

def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def event(obj):
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    obj["timestamp"] = obj.get("timestamp") or now()
    with EVENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def extract_json(text):
    text = text.strip()
    m = re.search(r"```(?:GPT_REPO_ACTION_V1|json)?\s*(\{.*?\})\s*```", text, re.S)
    if m:
        text = m.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start:end + 1]
    return json.loads(text)

def ingest_once():
    PASTEBOX.parent.mkdir(parents=True, exist_ok=True)
    INBOX.mkdir(parents=True, exist_ok=True)
    HISTORY.mkdir(parents=True, exist_ok=True)
    if not PASTEBOX.exists():
        PASTEBOX.write_text("", encoding="utf-8")
        print("BEM-GPT-INGRESS | PASTEBOX_CREATED")
        return 0

    raw = PASTEBOX.read_text(encoding="utf-8").strip()
    if not raw:
        print("BEM-GPT-INGRESS | NO_INPUT")
        return 0

    try:
        action = extract_json(raw)
    except Exception as exc:
        event({"event": "GPT_INGRESS_PARSE_FAILED", "error": str(exc)[:1000]})
        print("BEM-GPT-INGRESS | PARSE_FAILED")
        print(str(exc))
        return 1

    trace = action.get("trace_id") or ("ingress_" + now().replace(":", "").replace("-", ""))
    action["trace_id"] = trace
    target = INBOX / (trace + ".json")
    target.write_text(json.dumps(action, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    hist = HISTORY / (trace + ".txt")
    hist.write_text(raw + "\n", encoding="utf-8")
    PASTEBOX.write_text("", encoding="utf-8")

    event({"event": "GPT_INGRESS_ACTION_PLACED", "trace_id": trace, "target": str(target)})
    print("BEM-GPT-INGRESS | ACTION_PLACED")
    print("TRACE_ID=" + trace)
    print("TARGET=" + str(target))
    return 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--interval", type=int, default=5)
    args = ap.parse_args()
    if not args.once and not args.loop:
        raise SystemExit("use --once or --loop")

    while True:
        rc = ingest_once()
        if args.once:
            return rc
        time.sleep(args.interval)

if __name__ == "__main__":
    raise SystemExit(main())
