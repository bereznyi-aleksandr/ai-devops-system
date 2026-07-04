#!/usr/bin/env python3
"""DSM-1 trace-bound GitHub Actions lifecycle observer."""
import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "governance/state/dispatch_lifecycle.jsonl"
TASK = "BEM949-DSM-1"

def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def emit(value):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def event(trace, workflow, state, **extra):
    return {"protocol":"BEM-949","task_id":TASK,"observed_at":now(),
            "trace_id":trace,"workflow_id":workflow,"state":state,**extra}

def fetch(url, token):
    request = urllib.request.Request(url, headers={
        "Authorization":"Bearer "+token,
        "Accept":"application/vnd.github+json",
        "User-Agent":"ai-devops-dsm1",
    })
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8","replace")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        return exc.code, {}
    except Exception as exc:
        return 0, {"error":type(exc).__name__}

parser = argparse.ArgumentParser()
parser.add_argument("--confirm-only", action="store_true")
parser.add_argument("--record-dispatched", action="store_true")
parser.add_argument("--trace-id", required=True)
parser.add_argument("--dispatch-id", required=True)
parser.add_argument("--workflow-id", required=True)
parser.add_argument("--repository", required=True)
parser.add_argument("--poll-timeout-seconds", type=int, default=300)
parser.add_argument("--poll-interval-seconds", type=int, default=5)
parser.add_argument("--output", required=True)
args = parser.parse_args()
out = Path(args.output)
token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("AI_SYSTEM_GITHUB_PAT") or ""

def blocked(reason, run_id=None):
    result = {"status":"BLOCKED","task_id":TASK,"trace_id":args.trace_id,
              "result":{"blocker":reason,"run_id":run_id}}
    save(out, result)
    raise SystemExit(1)

if not args.confirm_only:
    blocked("confirm_only_required")
if not token or not args.repository:
    blocked("confirm_credentials_repository_or_workflow_missing")
if args.record_dispatched:
    emit(event(args.trace_id,args.workflow_id,"DISPATCHED",http_status=204))
encoded = urllib.parse.quote(args.workflow_id, safe="")
url = f"https://api.github.com/repos/{args.repository}/actions/workflows/{encoded}/runs?event=workflow_dispatch&per_page=100"
until = time.monotonic() + args.poll_timeout_seconds
run_id = None
while time.monotonic() < until:
    status, data = fetch(url, token)
    runs = data.get("workflow_runs", []) if status == 200 else []
    candidate = next((run for run in runs if isinstance(run,dict) and args.trace_id in " ".join(str(run.get(k) or "") for k in ("display_title","name","path"))), None)
    if candidate:
        if run_id is None:
            run_id = candidate.get("id")
            emit(event(args.trace_id,args.workflow_id,"START_CONFIRMED",run_id=run_id,
                       github_status=candidate.get("status"),html_url=candidate.get("html_url")))
        if candidate.get("status") == "completed":
            conclusion = str(candidate.get("conclusion") or "unknown")
            terminal = "COMPLETED" if conclusion == "success" else "FAILED"
            emit(event(args.trace_id,args.workflow_id,terminal,run_id=run_id,
                       conclusion=conclusion,html_url=candidate.get("html_url")))
            emit(event(args.trace_id,args.workflow_id,"STATE_COMMITEED",run_id=run_id,
                       terminal_state=terminal,conclusion=conclusion,commit_scope="dispatch_lifecycle_log"))
            result = {"status":"STATE_COMMITTED","task_id":TASK,"trace_id":args.trace_id,
                      "result":{"terminal_state":terminal,"conclusion":conclusion,
                                "run_id":run_id,"html_url":candidate.get("html_url")}}
            save(out,result)
            raise SystemExit(0 if conclusion == "success" else 1)
    time.sleep(args.poll_interval_seconds)
blocked("start_or_terminal_state_not_observed_before_timeout",run_id)
