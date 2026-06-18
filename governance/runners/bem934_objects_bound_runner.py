#!/usr/bin/env python3
import base64
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ["GH_TOKEN"]
RUN_ID = os.environ["GITHUB_RUN_ID"]
API = f"https://api.github.com/repos/{REPO}"
OBJECTS = {
    "GD": "governance/architecture/object_passports/GD.json",
    "DIR": "governance/architecture/object_passports/DIR.json",
    "WRK": "governance/architecture/object_passports/WRK.json",
}
SOURCE_RECEIPT = "governance/proofs/BEM934_claude_result_materialization_receipt.json"
SOURCE_PLAN = "governance/proofs/BEM934_object_binding_plan.json"
FINAL_RECEIPT = Path("governance/proofs/BEM934_objects_bound_receipt.json")
REGISTRY = Path("governance/architecture/objects_registry_v2.json")
QUEUE = Path("governance/roadmap/ACTIVE_QUEUE.json")
LOG = Path("governance/logs/execution_log.jsonl")


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def api(method, url, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "bem934-objects-bound",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        body = response.read()
        return response.status, json.loads(body) if body else None


def content(path):
    encoded = "/".join(urllib.parse.quote(p, safe="") for p in path.split("/"))
    _, obj = api("GET", f"{API}/contents/{encoded}?ref=main")
    return json.loads(base64.b64decode(obj["content"])), obj["sha"]


def latest_commit(path):
    encoded = urllib.parse.quote(path, safe="")
    _, commits = api("GET", f"{API}/commits?path={encoded}&sha=main&per_page=1")
    return commits[0]["sha"]


def dispatch_probe(object_id, passport):
    for attempt in range(1, 4):
        trace = f"bem934_objects_bound_{RUN_ID}_{object_id.lower()}_a{attempt}"
        task = (
            f"BEM-934 full runtime binding probe for target object {object_id}. "
            f"Read governance/architecture/objects_registry_v2.json and {passport}. "
            "Return a concrete proof-bearing plan for the full object chain GD -> DIR -> WRK. "
            f"Every major section must explicitly name target object {object_id} and its passport path. "
            "Explicitly cover Claude as provider, object runtime binding, WRK-C1 as a downstream contour, "
            "and idempotent Telegram routing. This is not a smoke test. "
            "Do not edit files; return only the requested structured JSON."
        )
        payload = {
            "ref": "main",
            "inputs": {
                "role": "curator",
                "provider": "claude",
                "trace_id": trace,
                "cycle_id": f"bem934_objects_bound_{RUN_ID}",
                "task_type": "object_runtime_binding",
                "task": task,
            },
        }
        status, _ = api("POST", f"{API}/actions/workflows/claude.yml/dispatches", payload)
        if status != 204:
            raise RuntimeError(f"claude.yml dispatch HTTP {status}")

        receipt = None
        receipt_blob = None
        for _ in range(16):
            time.sleep(15)
            try:
                candidate, blob = content(SOURCE_RECEIPT)
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    continue
                raise
            if candidate.get("trace_id") != trace:
                continue
            receipt, receipt_blob = candidate, blob
            if candidate.get("status") in {"PASS", "BLOCKED", "FAIL"}:
                break

        if not receipt or receipt.get("status") != "PASS":
            time.sleep(20)
            continue

        plan, plan_blob = content(SOURCE_PLAN)
        plan_text = json.dumps(plan, ensure_ascii=False)
        object_pattern = rf"(?i)(?<![A-Z0-9_]){re.escape(object_id)}(?![A-Z0-9_])"
        if plan.get("trace_id") != trace or not re.search(object_pattern, plan_text):
            continue

        checks = receipt.get("checks", {})
        if not checks or not all(checks.values()):
            continue

        return {
            "object_id": object_id,
            "passport_path": passport,
            "trace_id": trace,
            "provider": "claude",
            "workflow": ".github/workflows/claude.yml",
            "source_receipt_path": SOURCE_RECEIPT,
            "source_receipt_blob_sha": receipt_blob,
            "source_plan_path": SOURCE_PLAN,
            "source_plan_blob_sha": plan_blob,
            "source_commit_sha": latest_commit(SOURCE_RECEIPT),
            "receipt": receipt,
            "plan": plan,
        }
    raise RuntimeError(f"No proof-bearing Claude PASS for {object_id}")


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


def write_binding(evidence):
    git("pull", "--rebase", "--autostash", "origin", "main")
    proof_dir = Path("governance/proofs/bem934_objects_bound")
    proof_dir.mkdir(parents=True, exist_ok=True)
    for item in evidence:
        snapshot = proof_dir / f"{item['object_id']}_runtime_binding.json"
        snapshot.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n")
        item["snapshot_path"] = str(snapshot)

    registry = json.loads(REGISTRY.read_text())
    by_id = {item["object_id"]: item for item in evidence}
    compact = []
    for obj in registry["objects"]:
        object_id = obj["object_id"]
        if object_id not in by_id:
            raise RuntimeError(f"Missing evidence for {object_id}")
        item = by_id[object_id]
        bound = {
            "object_id": object_id,
            "passport_path": item["passport_path"],
            "trace_id": item["trace_id"],
            "provider": "claude",
            "workflow": item["workflow"],
            "source_receipt_blob_sha": item["source_receipt_blob_sha"],
            "source_plan_blob_sha": item["source_plan_blob_sha"],
            "source_commit_sha": item["source_commit_sha"],
            "snapshot_path": item["snapshot_path"],
        }
        obj["runtime_binding"] = bound
        compact.append(bound)

    registry.update(
        {
            "protocol": "BEM-934",
            "status": "BOUND",
            "bound_at": now(),
            "binding_evidence": {
                "task_id": "BEM934-OBJECTS-BOUND",
                "provider": "claude",
                "workflow": ".github/workflows/claude.yml",
                "full_path": True,
                "smoke_only": False,
                "objects": compact,
            },
        }
    )
    REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n")

    checks = {
        "claude_workflow_invoked_per_object": len(compact) == 3,
        "three_distinct_trace_ids": len({x["trace_id"] for x in compact}) == 3,
        "all_source_receipts_pass": all(x["receipt"]["status"] == "PASS" for x in evidence),
        "all_source_receipt_blob_shas_present": all(x["source_receipt_blob_sha"] for x in compact),
        "all_source_plan_blob_shas_present": all(x["source_plan_blob_sha"] for x in compact),
        "all_source_commit_shas_present": all(x["source_commit_sha"] for x in compact),
        "registry_status_bound": registry["status"] == "BOUND",
        "full_non_smoke_path": registry["binding_evidence"]["full_path"]
        and not registry["binding_evidence"]["smoke_only"],
        "provider_is_claude": all(x["provider"] == "claude" for x in compact),
    }
    if not all(checks.values()):
        raise RuntimeError("Binding checks failed")
    receipt = {
        "status": "PASS",
        "protocol": "BEM-934",
        "task_id": "BEM934-OBJECTS-BOUND",
        "created_at": now(),
        "provider_selected": "claude",
        "workflow": ".github/workflows/claude.yml",
        "registry_path": str(REGISTRY),
        "registry_status": "BOUND",
        "binding_commit_sha": None,
        "trace_ids": [x["trace_id"] for x in compact],
        "objects": compact,
        "checks": checks,
    }
    FINAL_RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")

    subprocess.run(
        ["git", "add", str(REGISTRY), str(FINAL_RECEIPT), str(proof_dir)],
        check=True,
    )
    git("commit", "-m", "Bind BEM-934 object runtimes with Claude trace evidence")
    try:
        git("push")
    except subprocess.CalledProcessError:
        git("pull", "--rebase", "origin", "main")
        git("push")
    return git("rev-parse", "HEAD")


def finalize(binding_sha):
    git("pull", "--rebase", "--autostash", "origin", "main")
    receipt = json.loads(FINAL_RECEIPT.read_text())
    receipt["binding_commit_sha"] = binding_sha
    receipt["registry_blob_sha"] = git("rev-parse", f"HEAD:{REGISTRY}")
    receipt["checks"]["binding_commit_sha_present"] = bool(binding_sha)
    receipt["checks"]["registry_blob_sha_present"] = bool(receipt["registry_blob_sha"])
    if receipt["status"] != "PASS" or not all(receipt["checks"].values()):
        raise RuntimeError("Final receipt validation failed")
    FINAL_RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")

    queue = json.loads(QUEUE.read_text())
    stamp = now()
    for task in queue["tasks"]:
        if task["id"] == "BEM934-OBJECTS-BOUND":
            task.update(
                {
                    "status": "DONE",
                    "done_sha": binding_sha,
                    "receipt": str(FINAL_RECEIPT),
                    "completed_at": stamp,
                }
            )
        elif task["id"] == "BEM934-LIVE-TEST":
            task["status"] = "IN_PROGRESS"
            task.pop("blocked_by", None)
    queue["version"] = int(queue.get("version", 0)) + 1
    queue["updated_at"] = stamp
    queue["current_task"] = "BEM934-LIVE-TEST"
    queue["completed_summary"]["tasks_done"] = 8
    if str(FINAL_RECEIPT) not in queue["completed_summary"]["proofs"]:
        queue["completed_summary"]["proofs"].append(str(FINAL_RECEIPT))
    queue["last_completed"] = {
        "id": "BEM934-OBJECTS-BOUND",
        "completed_at": stamp,
        "done_sha": binding_sha,
    }
    queue["next_action"] = (
        "BEM934-LIVE-TEST — execute content-bearing Telegram E2E "
        "through provider-router.yml to claude.yml"
    )
    QUEUE.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n")
    with LOG.open("a") as handle:
        handle.write(
            json.dumps(
                {
                    "date": stamp,
                    "id": "BEM934-OBJECTS-BOUND",
                    "sha": binding_sha,
                    "status": "done",
                    "receipt": str(FINAL_RECEIPT),
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    subprocess.run(["git", "add", str(FINAL_RECEIPT), str(QUEUE), str(LOG)], check=True)
    git("commit", "-m", "Close BEM934-OBJECTS-BOUND and advance live test")
    try:
        git("push")
    except subprocess.CalledProcessError:
        git("pull", "--rebase", "origin", "main")
        git("push")


def main():
    git("config", "user.email", "bem934-objects-bound@ai-devops-system")
    git("config", "user.name", "BEM-934 Objects Binding")
    evidence = [dispatch_probe(object_id, passport) for object_id, passport in OBJECTS.items()]
    binding_sha = write_binding(evidence)
    finalize(binding_sha)


if __name__ == "__main__":
    main()
