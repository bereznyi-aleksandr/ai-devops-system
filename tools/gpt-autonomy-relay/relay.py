#!/usr/bin/env python3
import argparse, json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path.cwd()
POLICY = ROOT / "governance/policies/gpt_autonomy_relay_policy.json"
EVENTS = ROOT / "governance/events/gpt_autonomy_relay_events.jsonl"

def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def die(msg):
    print("BEM-GPT-AUTONOMY-RELAY | FAIL | " + msg)
    sys.exit(1)

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def allowed_path(p, policy):
    p = p.replace("\\", "/").lstrip("/")
    for denied in policy["denied_paths"]:
        if denied in p:
            return False
    return any(p.startswith(prefix) for prefix in policy["allowed_paths"])

def event(obj):
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def validate(action, policy):
    for field in ["version", "trace_id", "source", "operation", "files", "commit_message"]:
        if field not in action:
            die("missing_field:" + field)
    if action["source"] != "external_gpt_chat":
        die("bad_source")
    if action["operation"] not in policy["allowed_operations"]:
        die("bad_operation")
    if len(action["files"]) > policy["max_files_per_action"]:
        die("too_many_files")
    for item in action["files"]:
        path = item["path"]
        op = item.get("action", action["operation"])
        if op not in policy["allowed_operations"]:
            die("bad_file_operation:" + op)
        if not allowed_path(path, policy):
            die("path_not_allowed:" + path)

def apply(action, dry):
    for item in action["files"]:
        path = ROOT / item["path"]
        op = item.get("action", action["operation"])
        content = item.get("content", "")
        print(("[DRY] " if dry else "[APPLY] ") + op + " " + item["path"])
        if dry:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if op == "create_file" and path.exists():
            die("file_exists:" + item["path"])
        if op in ("create_file", "update_file"):
            path.write_text(content, encoding="utf-8")
        elif op == "append_file":
            with path.open("a", encoding="utf-8") as f:
                f.write(content)
                if content and not content.endswith("\n"):
                    f.write("\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--action-file", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    if not args.dry_run and not args.apply:
        die("use --dry-run or --apply")

    policy = load(POLICY)
    action = load(args.action_file)
    validate(action, policy)

    base = {
        "timestamp": now(),
        "trace_id": action["trace_id"],
        "source": action["source"],
        "operation": action["operation"],
        "dry_run": args.dry_run,
        "files": [x["path"] for x in action["files"]]
    }

    event({**base, "event": "GPT_RELAY_ACTION_ACCEPTED"})
    apply(action, args.dry_run)
    event({**base, "event": "GPT_RELAY_DRY_RUN_OK" if args.dry_run else "GPT_RELAY_APPLIED"})

    if not args.dry_run:
        subprocess.run("python3 -m compileall scripts tools/gpt-autonomy-relay", shell=True, check=True)

    print("BEM-GPT-AUTONOMY-RELAY | " + ("DRY_RUN_OK" if args.dry_run else "APPLY_OK"))

if __name__ == "__main__":
    main()
