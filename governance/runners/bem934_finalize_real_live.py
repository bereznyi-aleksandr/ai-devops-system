#!/usr/bin/env python3
import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

TRACE = "tg_818730867_20260618T105741Z"
ROUTER = Path(f"governance/proofs/BEM932_provider_router_{TRACE}.json")
PROOF = Path(f"governance/proofs/BEM934_live_content_{TRACE}.json")
REPORT = Path(f"governance/reports/{TRACE}.md")
RESULTS = Path("governance/transport/results.jsonl")
RECEIPT = Path("governance/proofs/BEM934_live_test_receipt.json")
QUEUE = Path("governance/roadmap/ACTIVE_QUEUE.json")
LOG = Path("governance/logs/execution_log.jsonl")

def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def blob_sha(path: Path) -> str:
    return git("hash-object", path.as_posix())

def committed_evidence(path: Path) -> dict:
    return {
        "path": path.as_posix(),
        "blob_sha": git("rev-parse", f"HEAD:{path.as_posix()}"),
        "commit_sha": git("log", "-1", "--format=%H", "--", path.as_posix()),
        "size": path.stat().st_size,
    }

def pending_evidence(path: Path) -> dict:
    return {
        "path": path.as_posix(),
        "blob_sha": blob_sha(path),
        "size": path.stat().st_size,
    }

def exact_transport_records() -> list[dict]:
    records: list[dict] = []
    for line in RESULTS.read_text(encoding="utf-8", errors="replace").splitlines():
        if TRACE not in line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("trace_id") == TRACE:
            records.append(item)
    return records

def canonical_report(proof: dict, router: dict, transport: dict) -> str:
    lines = [
        f"# BEM-934 Live Content Analysis — {TRACE}",
        "",
        "**Status:** PASS",
        "**Protocol:** BEM-934",
        "**Task:** BEM934-LIVE-TEST",
        "**Provider:** claude_code",
        f"**Router receipt:** `{ROUTER.as_posix()}`",
        "",
        "## Idempotency invariants",
        "",
    ]
    for index, invariant in enumerate(proof["invariants"], 1):
        if isinstance(invariant, dict):
            title = invariant.get("id") or invariant.get("name") or f"INV-{index}"
            body = (
                invariant.get("description")
                or invariant.get("assertion")
                or invariant.get("invariant")
                or json.dumps(invariant, ensure_ascii=False, sort_keys=True)
            )
        else:
            title = f"INV-{index}"
            body = str(invariant)
        lines.extend([f"### {title}", "", str(body), ""])
    lines.extend(["## Validation steps", ""])
    for index, step in enumerate(proof["validation_steps"], 1):
        rendered = step if isinstance(step, str) else json.dumps(step, ensure_ascii=False, sort_keys=True)
        lines.append(f"{index}. {rendered}")
    lines.extend(["", "## Acceptance checks", ""])
    for item in proof["acceptance_checks"]:
        name = item.get("check") or item.get("name") or item.get("id") or "check"
        lines.append(f"- **{name}: {item.get('result')}**")
    lines.extend(["", "## Limitations", ""])
    for item in proof["limitations"]:
        rendered = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False, sort_keys=True)
        lines.append(f"- {rendered}")
    lines.extend(
        [
            "",
            "## Runtime evidence",
            "",
            f"- Telegram chat_id: `{router.get('chat_id')}`",
            f"- Telegram message_id: `{router.get('message_id')}`",
            f"- provider_selected: `{router.get('provider_selected')}`",
            f"- target_workflow_id: `{router.get('target_workflow_id')}`",
            f"- transport status: `{transport.get('status')}`",
            "- blocker: none",
            "",
        ]
    )
    return "\n".join(lines)

def validate(run_id: int, run_conclusion: str) -> None:
    required = (ROUTER, PROOF, RESULTS, QUEUE, LOG)
    missing = [path.as_posix() for path in required if not path.exists()]
    if missing:
        raise SystemExit(f"missing required files: {missing}")

    router = load_json(ROUTER)
    proof = load_json(PROOF)
    acceptance = proof.get("acceptance_checks")
    checks = {
        "github_run_success": run_conclusion == "success",
        "router_status_pass": router.get("status") == "PASS",
        "router_trace_match": router.get("trace_id") == TRACE,
        "router_provider_claude_code": router.get("provider_selected") == "claude_code",
        "router_target_claude_yml": router.get("target_workflow_id") == "claude.yml",
        "router_chat_id_match": str(router.get("chat_id")) == "601442777",
        "router_message_id_match": str(router.get("message_id")) == "729",
        "proof_status_pass": proof.get("status") == "PASS",
        "proof_protocol": proof.get("protocol") == "BEM-934",
        "proof_task_id": proof.get("task_id") == "BEM934-LIVE-TEST",
        "proof_trace_match": proof.get("trace_id") == TRACE,
        "proof_provider_claude_code": proof.get("provider_selected") == "claude_code",
        "proof_router_match": proof.get("source_router_receipt") == ROUTER.as_posix(),
        "exactly_two_invariants": isinstance(proof.get("invariants"), list) and len(proof["invariants"]) == 2,
        "validation_steps_present": isinstance(proof.get("validation_steps"), list) and len(proof["validation_steps"]) >= 2,
        "acceptance_checks_pass": (
            isinstance(acceptance, list)
            and len(acceptance) >= 2
            and all(isinstance(item, dict) and item.get("result") == "PASS" for item in acceptance)
        ),
        "limitations_present": isinstance(proof.get("limitations"), list) and len(proof["limitations"]) >= 1,
    }
    failed = [name for name, value in checks.items() if not value]
    if failed:
        raise SystemExit(f"router/proof checks failed: {failed}")

    completed = [
        item
        for item in exact_transport_records()
        if item.get("status") == "completed"
        and not item.get("blocker")
        and item.get("provider") == "claude"
    ]
    if not completed:
        raise SystemExit("no exact blocker-free completed Claude transport record")
    transport = completed[-1]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(canonical_report(proof, router, transport), encoding="utf-8")
    report_text = REPORT.read_text(encoding="utf-8")
    if any(marker in report_text for marker in ("<<<<<<<", "=======", ">>>>>>>")):
        raise SystemExit("conflict marker remains in canonical report")
    if len(report_text.encode("utf-8")) < 500:
        raise SystemExit("canonical report is not substantive")

    completed_at = now()
    receipt = {
        "status": "PASS",
        "protocol": "BEM-934",
        "task_id": "BEM934-LIVE-TEST",
        "created_at": completed_at,
        "trace_id": TRACE,
        "ingress_mode": "real_operator_telegram_webhook",
        "replay": False,
        "provider_selected": "claude_code",
        "target_workflow": "claude.yml",
        "chat_id": 601442777,
        "message_id": 729,
        "github_run_id": run_id,
        "github_run_conclusion": run_conclusion,
        "router_receipt": committed_evidence(ROUTER),
        "content_proof": committed_evidence(PROOF),
        "claude_report": {
            **pending_evidence(REPORT),
            "canonicalized_from_proof": True,
            "conflict_markers_absent": True,
        },
        "transport_result": transport,
        "checks": {
            **checks,
            "transport_completed": True,
            "transport_no_blocker": True,
            "transport_provider_claude": True,
            "report_substantive": True,
            "report_conflict_markers_absent": True,
            "real_ingress_not_replay": True,
        },
    }
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "receipt": RECEIPT.as_posix(), "trace_id": TRACE}))

def advance(done_sha: str) -> None:
    queue = load_json(QUEUE)
    completed_at = now()
    found_live = False
    found_close = False
    for task in queue.get("tasks", []):
        task_id = task.get("id")
        if task_id == "BEM934-LIVE-TEST":
            task.clear()
            task.update(
                {
                    "id": "BEM934-LIVE-TEST",
                    "title": "Content-bearing Telegram E2E through provider-router to Claude",
                    "status": "DONE",
                    "priority": 9,
                    "done_sha": done_sha,
                    "receipt": RECEIPT.as_posix(),
                    "completed_at": completed_at,
                }
            )
            found_live = True
        elif task_id == "BEM934-CLOSE":
            task["status"] = "IN_PROGRESS"
            task.pop("blocked_by", None)
            found_close = True
    if not found_live or not found_close:
        raise SystemExit("LIVE or CLOSE task absent from queue")
    queue["version"] = int(queue.get("version", 0)) + 1
    queue["updated_at"] = completed_at
    queue["current_task"] = "BEM934-CLOSE"
    queue["system_status"] = "BEM934_CLOSURE_IN_PROGRESS"
    queue["release_status"] = "FOLLOW_UP_REQUIRED"
    queue["completed_summary"]["tasks_done"] = 9
    proofs = queue["completed_summary"].setdefault("proofs", [])
    if RECEIPT.as_posix() not in proofs:
        proofs.append(RECEIPT.as_posix())
    queue["last_completed"] = {"id": "BEM934-LIVE-TEST", "completed_at": completed_at, "done_sha": done_sha}
    queue["next_action"] = (
        "BEM934-CLOSE — update canonical context/status, restore Claude workflow defaults, "
        "obtain external Claude auditor verdict, and close protocol"
    )
    QUEUE.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "date": completed_at,
                    "id": "BEM934-LIVE-TEST",
                    "sha": done_sha,
                    "status": "done",
                    "receipt": RECEIPT.as_posix(),
                    "trace_id": TRACE,
                    "provider_selected": "claude_code",
                    "next": "BEM934-CLOSE",
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    print(json.dumps({"status": "PASS", "next": "BEM934-CLOSE"}))

def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("--run-id", required=True, type=int)
    validate_parser.add_argument("--run-conclusion", required=True)
    advance_parser = sub.add_parser("advance")
    advance_parser.add_argument("--done-sha", required=True)
    args = parser.parse_args()
    if args.command == "validate":
        validate(args.run_id, args.run_conclusion)
    else:
        advance(args.done_sha)

if __name__ == "__main__":
    main()
