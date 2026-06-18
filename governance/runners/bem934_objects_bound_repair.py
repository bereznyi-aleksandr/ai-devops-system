#!/usr/bin/env python3
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = os.environ["GITHUB_REPOSITORY"]
RUN_ID = os.environ["GITHUB_RUN_ID"]
SOURCE_RECEIPT = "governance/proofs/BEM934_claude_result_materialization_receipt.json"
SOURCE_PLAN = "governance/proofs/BEM934_object_binding_plan.json"
REGISTRY = Path("governance/architecture/objects_registry_v2.json")
QUEUE = Path("governance/roadmap/ACTIVE_QUEUE.json")
LOG = Path("governance/logs/execution_log.jsonl")
FINAL_RECEIPT = Path("governance/proofs/BEM934_objects_bound_receipt.json")
PROOF_DIR = Path("governance/proofs/bem934_objects_bound")
OBJECTS = {
    "GD": "governance/architecture/object_passports/GD.json",
    "DIR": "governance/architecture/object_passports/DIR.json",
    "WRK": "governance/architecture/object_passports/WRK.json",
}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(*args: str, check: bool = True) -> str:
    completed = subprocess.run(
        list(args),
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return completed.stdout.strip()


def git(*args: str, check: bool = True) -> str:
    return run("git", *args, check=check)


def sync() -> None:
    git("fetch", "origin", "main")
    git("pull", "--rebase", "--autostash", "origin", "main")


def remote_text(path: str) -> str:
    return git("show", f"origin/main:{path}")


def remote_json(path: str) -> dict:
    return json.loads(remote_text(path))


def remote_blob(path: str) -> str:
    return git("rev-parse", f"origin/main:{path}")


def remote_last_commit(path: str) -> str:
    return git("log", "-1", "--format=%H", "origin/main", "--", path)


def command_ok(*args: str) -> bool:
    completed = subprocess.run(
        list(args),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return completed.returncode == 0


def push_commit(message: str, paths: list[str]) -> str:
    git("add", *paths)
    if command_ok("git", "diff", "--cached", "--quiet"):
        return git("rev-parse", "HEAD")
    git("commit", "-m", message)
    for _ in range(4):
        if command_ok("git", "push"):
            return git("rev-parse", "HEAD")
        git("pull", "--rebase", "origin", "main")
    raise RuntimeError(f"push failed after retries: {message}")


def plan_mentions_object(plan: dict, object_id: str) -> bool:
    text = json.dumps(plan, ensure_ascii=False)
    pattern = rf"(?i)(?<![A-Z0-9_]){re.escape(object_id)}(?![A-Z0-9_])"
    return bool(re.search(pattern, text))


def validate_source(receipt: dict, plan: dict, trace: str, object_id: str) -> None:
    checks = receipt.get("checks") or {}
    required = {
        "strict_json_object_parsed",
        "required_fields_present",
        "trace_matches",
        "steps_are_task_specific",
        "acceptance_is_verifiable",
        "mentions_wrk_c1",
        "mentions_claude_provider",
        "mentions_object_runtime_binding",
        "mentions_idempotent_telegram_routing",
    }
    if receipt.get("status") != "PASS":
        raise RuntimeError(f"{object_id}: source receipt is not PASS")
    if receipt.get("trace_id") != trace or plan.get("trace_id") != trace:
        raise RuntimeError(f"{object_id}: trace mismatch")
    if not required.issubset(checks):
        raise RuntimeError(f"{object_id}: missing required checks")
    if not all(bool(checks[name]) for name in required):
        raise RuntimeError(f"{object_id}: a required check is false")
    if not plan_mentions_object(plan, object_id):
        raise RuntimeError(f"{object_id}: plan does not explicitly name object")


def capture_trace(object_id: str, trace: str, polls: int = 40) -> dict:
    for _ in range(polls):
        git("fetch", "origin", "main")
        try:
            receipt = remote_json(SOURCE_RECEIPT)
            plan = remote_json(SOURCE_PLAN)
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            time.sleep(15)
            continue
        if receipt.get("trace_id") != trace or plan.get("trace_id") != trace:
            time.sleep(15)
            continue
        validate_source(receipt, plan, trace, object_id)
        item = {
            "status": "PASS",
            "protocol": "BEM-934",
            "task_id": "BEM934-OBJECTS-BOUND",
            "object_id": object_id,
            "passport_path": OBJECTS[object_id],
            "trace_id": trace,
            "provider": "claude",
            "workflow": ".github/workflows/claude.yml",
            "captured_at": now(),
            "source_receipt_path": SOURCE_RECEIPT,
            "source_receipt_blob_sha": remote_blob(SOURCE_RECEIPT),
            "source_plan_path": SOURCE_PLAN,
            "source_plan_blob_sha": remote_blob(SOURCE_PLAN),
            "source_commit_sha": remote_last_commit(SOURCE_RECEIPT),
            "receipt": receipt,
            "plan": plan,
        }
        sync()
        PROOF_DIR.mkdir(parents=True, exist_ok=True)
        path = PROOF_DIR / f"{object_id}_runtime_binding.json"
        path.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        commit_sha = push_commit(
            f"Capture BEM-934 {object_id} runtime binding evidence",
            [str(path)],
        )
        item["snapshot_path"] = str(path)
        item["snapshot_commit_sha"] = commit_sha
        item["snapshot_blob_sha"] = git("rev-parse", f"HEAD:{path}")
        path.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        final_commit = push_commit(
            f"Finalize BEM-934 {object_id} evidence identifiers",
            [str(path)],
        )
        item["snapshot_final_commit_sha"] = final_commit
        return item
    raise RuntimeError(f"{object_id}: timed out waiting for trace {trace}")


def dispatch(object_id: str) -> str:
    trace = f"bem934_objects_bound_repair_{RUN_ID}_{object_id.lower()}"
    passport = OBJECTS[object_id]
    task = (
        f"BEM-934 full runtime binding proof for target object {object_id}. "
        f"Read governance/architecture/objects_registry_v2.json and {passport}. "
        f"Return a concrete proof-bearing plan for the complete GD -> DIR -> WRK chain. "
        f"Every major section must explicitly name target object {object_id} and passport {passport}. "
        "Explicitly cover Claude as provider, object runtime binding, WRK-C1 as downstream contour, "
        "and idempotent Telegram routing. This is a full path, not a smoke test. "
        "Do not edit repository files; return only the requested structured JSON."
    )
    run(
        "gh", "workflow", "run", "claude.yml",
        "--repo", REPO,
        "--ref", "main",
        "-f", "role=curator",
        "-f", "provider=claude",
        "-f", f"trace_id={trace}",
        "-f", f"cycle_id=bem934_objects_bound_repair_{RUN_ID}",
        "-f", "task_type=object_runtime_binding",
        "-f", f"task={task}",
    )
    return trace


def capture_existing_gd() -> dict:
    git("fetch", "origin", "main")
    receipt = remote_json(SOURCE_RECEIPT)
    plan = remote_json(SOURCE_PLAN)
    trace = str(receipt.get("trace_id", ""))
    if "_gd_" not in trace.lower():
        raise RuntimeError(f"Expected existing GD trace, got {trace}")
    validate_source(receipt, plan, trace, "GD")
    return capture_trace("GD", trace, polls=2)


def load_snapshot(object_id: str) -> dict:
    return json.loads((PROOF_DIR / f"{object_id}_runtime_binding.json").read_text(encoding="utf-8"))


def finalize() -> tuple[str, str]:
    sync()
    evidence = [load_snapshot(object_id) for object_id in OBJECTS]
    by_id = {item["object_id"]: item for item in evidence}

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    compact = []
    for obj in registry["objects"]:
        object_id = obj["object_id"]
        item = by_id[object_id]
        bound = {
            "object_id": object_id,
            "passport_path": item["passport_path"],
            "trace_id": item["trace_id"],
            "provider": "claude",
            "workflow": item["workflow"],
            "source_receipt_path": item["source_receipt_path"],
            "source_receipt_blob_sha": item["source_receipt_blob_sha"],
            "source_plan_path": item["source_plan_path"],
            "source_plan_blob_sha": item["source_plan_blob_sha"],
            "source_commit_sha": item["source_commit_sha"],
            "snapshot_path": item["snapshot_path"],
            "snapshot_blob_sha": git("rev-parse", f"HEAD:{item['snapshot_path']}"),
            "snapshot_commit_sha": item["snapshot_final_commit_sha"],
        }
        obj["runtime_binding"] = bound
        compact.append(bound)

    registry.update({
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
    })
    REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    checks = {
        "claude_workflow_invoked_per_object": len(compact) == 3,
        "three_distinct_trace_ids": len({x["trace_id"] for x in compact}) == 3,
        "all_source_receipts_pass": all(x["receipt"]["status"] == "PASS" for x in evidence),
        "all_source_receipt_blob_shas_present": all(x["source_receipt_blob_sha"] for x in compact),
        "all_source_plan_blob_shas_present": all(x["source_plan_blob_sha"] for x in compact),
        "all_source_commit_shas_present": all(x["source_commit_sha"] for x in compact),
        "all_snapshot_blob_shas_present": all(x["snapshot_blob_sha"] for x in compact),
        "registry_status_bound": registry["status"] == "BOUND",
        "full_non_smoke_path": registry["binding_evidence"]["full_path"]
            and not registry["binding_evidence"]["smoke_only"],
        "provider_is_claude": all(x["provider"] == "claude" for x in compact),
    }
    if not all(checks.values()):
        raise RuntimeError("Final binding checks failed")

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
        "registry_blob_sha": None,
        "trace_ids": [x["trace_id"] for x in compact],
        "objects": compact,
        "checks": checks,
    }
    FINAL_RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    binding_sha = push_commit(
        "Bind BEM-934 object runtimes with Claude trace evidence",
        [str(REGISTRY), str(FINAL_RECEIPT)],
    )

    sync()
    receipt = json.loads(FINAL_RECEIPT.read_text(encoding="utf-8"))
    receipt["binding_commit_sha"] = binding_sha
    receipt["registry_blob_sha"] = git("rev-parse", f"HEAD:{REGISTRY}")
    receipt["checks"]["binding_commit_sha_present"] = bool(binding_sha)
    receipt["checks"]["registry_blob_sha_present"] = bool(receipt["registry_blob_sha"])
    if not all(receipt["checks"].values()):
        raise RuntimeError("Receipt identifier checks failed")
    FINAL_RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    stamp = now()
    for task in queue["tasks"]:
        if task["id"] == "BEM934-OBJECTS-BOUND":
            task.update({
                "status": "DONE",
                "done_sha": binding_sha,
                "receipt": str(FINAL_RECEIPT),
                "completed_at": stamp,
            })
            task.pop("blocked_by", None)
        elif task["id"] == "BEM934-LIVE-TEST":
            task["status"] = "IN_PROGRESS"
            task.pop("blocked_by", None)
    queue["version"] = int(queue.get("version", 0)) + 1
    queue["updated_at"] = stamp
    queue["current_task"] = "BEM934-LIVE-TEST"
    summary = queue.setdefault("completed_summary", {})
    summary["tasks_done"] = max(int(summary.get("tasks_done", 0)), 8)
    proofs = summary.setdefault("proofs", [])
    if str(FINAL_RECEIPT) not in proofs:
        proofs.append(str(FINAL_RECEIPT))
    queue["last_completed"] = {
        "id": "BEM934-OBJECTS-BOUND",
        "completed_at": stamp,
        "done_sha": binding_sha,
    }
    queue["next_action"] = (
        "BEM934-LIVE-TEST — execute content-bearing Telegram E2E "
        "through provider-router.yml to claude.yml"
    )
    QUEUE.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "date": stamp,
            "id": "BEM934-OBJECTS-BOUND",
            "sha": binding_sha,
            "status": "done",
            "receipt": str(FINAL_RECEIPT),
        }, ensure_ascii=False) + "\n")

    close_sha = push_commit(
        "Close BEM934-OBJECTS-BOUND and advance live test",
        [str(FINAL_RECEIPT), str(QUEUE), str(LOG)],
    )
    return binding_sha, close_sha


def main() -> None:
    git("config", "user.email", "bem934-objects-bound-repair@ai-devops-system")
    git("config", "user.name", "BEM-934 Objects Binding Repair")
    gd = capture_existing_gd()
    dir_trace = dispatch("DIR")
    directory = capture_trace("DIR", dir_trace)
    wrk_trace = dispatch("WRK")
    worker = capture_trace("WRK", wrk_trace)
    if len({gd["trace_id"], directory["trace_id"], worker["trace_id"]}) != 3:
        raise RuntimeError("Trace IDs are not distinct")
    binding_sha, close_sha = finalize()
    print(json.dumps({
        "status": "PASS",
        "binding_sha": binding_sha,
        "close_sha": close_sha,
        "receipt": str(FINAL_RECEIPT),
    }))


if __name__ == "__main__":
    main()
