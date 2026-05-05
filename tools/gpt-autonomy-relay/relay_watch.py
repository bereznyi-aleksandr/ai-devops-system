#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
INBOX = ROOT / "governance/state/gpt_relay_inbox"
DONE = ROOT / "governance/state/gpt_relay_done"
FAILED = ROOT / "governance/state/gpt_relay_failed"
EVENTS = ROOT / "governance/events/gpt_autonomy_relay_watch.jsonl"
STATE = ROOT / "governance/state/gpt_relay_watch_state.json"
RELAY = ROOT / "tools/gpt-autonomy-relay/relay.py"

def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def event(obj):
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    obj["timestamp"] = obj.get("timestamp") or now()
    with EVENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def state(status, current=None, error=None):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({
        "version": 1,
        "status": status,
        "updated_at": now(),
        "current_action": str(current) if current else None,
        "last_error": error
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def run(cmd):
    print("$ " + cmd)
    subprocess.run(cmd, shell=True, check=True)

def next_action():
    INBOX.mkdir(parents=True, exist_ok=True)
    files = sorted(INBOX.glob("*.json"))
    return files[0] if files else None

def process(path, push):
    action = json.loads(path.read_text(encoding="utf-8"))
    trace = action.get("trace_id", path.stem)
    msg = action.get("commit_message", "GPT relay watch action " + trace)

    event({"event": "GPT_RELAY_WATCH_ACTION_STARTED", "trace_id": trace, "file": str(path)})
    state("running", path)

    run(f"python3 {RELAY} --action-file {path} --dry-run")
    run(f"python3 {RELAY} --action-file {path} --apply")
    run("python3 -m compileall scripts tools/gpt-autonomy-relay")
    run("git add governance scripts tools .github || true")

    if subprocess.run("git diff --cached --quiet", shell=True).returncode != 0:
        run(f'git commit -m "{msg}"')
        run("git pull --rebase --autostash origin main")
        if push:
            run("git push origin HEAD:main")

    DONE.mkdir(parents=True, exist_ok=True)
    target = DONE / path.name
    shutil.move(str(path), str(target))
    event({"event": "GPT_RELAY_WATCH_ACTION_DONE", "trace_id": trace, "done_file": str(target), "pushed": push})
    state("idle")
    print("BEM-GPT-RELAY-WATCH | ACTION_DONE")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--interval", type=int, default=10)
    ap.add_argument("--no-push", action="store_true")
    args = ap.parse_args()

    if not args.once and not args.loop:
        raise SystemExit("use --once or --loop")

    for d in (INBOX, DONE, FAILED):
        d.mkdir(parents=True, exist_ok=True)

    state("idle")
    event({"event": "GPT_RELAY_WATCH_STARTED", "mode": "loop" if args.loop else "once"})

    while True:
        path = next_action()
        if not path:
            print("BEM-GPT-RELAY-WATCH | NO_ACTION")
            if args.once:
                return 0
            time.sleep(args.interval)
            continue
        try:
            process(path, push=not args.no_push)
            if args.once:
                return 0
        except Exception as exc:
            FAILED.mkdir(parents=True, exist_ok=True)
            target = FAILED / path.name
            shutil.move(str(path), str(target))
            event({"event": "GPT_RELAY_WATCH_ACTION_FAILED", "file": str(target), "error": str(exc)[:1000]})
            state("failed", target, str(exc)[:1000])
            print("BEM-GPT-RELAY-WATCH | ACTION_FAILED")
            print(str(exc))
            return 1

if __name__ == "__main__":
    raise SystemExit(main())
