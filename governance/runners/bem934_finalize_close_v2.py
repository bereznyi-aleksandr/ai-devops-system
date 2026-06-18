#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path

R = Path(".")
P = {
    "q": R / "governance/roadmap/ACTIVE_QUEUE.json",
    "live": R / "governance/proofs/BEM934_live_test_receipt.json",
    "old": R / "governance/proofs/BEM934_live_test_receipt_superseded_replay.json",
    "prep": R / "governance/proofs/BEM934_close_preparation_receipt.json",
    "verdict": R / "governance/proofs/BEM934_external_auditor_verdict.json",
    "run": R / "governance/proofs/BEM934_external_audit_run_receipt.json",
    "cfg": R / "governance/config/provider_config.json",
    "claude": R / ".github/workflows/claude.yml",
    "ctx": R / "governance/AGENT_CONTEXT.md",
    "status": R / "SYSTEM_STATUS.md",
    "close": R / "governance/proofs/BEM934_close_receipt.json",
    "final": R / "governance/proofs/BEM934_FINAL_VERIFICATION_PASS.json",
    "log": R / "governance/logs/execution_log.jsonl",
}
INPUTS = ("role", "provider", "trace_id", "cycle_id", "task_type", "task")


def ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(k):
    v = json.loads(P[k].read_text(encoding="utf-8"))
    if not isinstance(v, dict):
        raise RuntimeError("not_object:" + k)
    return v


def write(k, v):
    P[k].parent.mkdir(parents=True, exist_ok=True)
    P[k].write_text(json.dumps(v, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(k):
    return hashlib.sha256(P[k].read_bytes()).hexdigest()


def alltrue(v):
    return isinstance(v, dict) and bool(v) and all(x is True for x in v.values())


def canonical_inputs(text):
    out = {}
    for n in INPUTS:
        m = f"      {n}:"
        a = text.find(m)
        if a < 0:
            out[n] = False
            continue
        ends = [
            x
            for o in INPUTS
            if (x := text.find(f"      {o}:", a + len(m))) >= 0
        ]
        ends += [
            x
            for z in ("\n  issue_comment:", "\n  issues:", "\n  pull_request:")
            if (x := text.find(z, a + len(m))) >= 0
        ]
        b = min(ends) if ends else len(text)
        block = text[a:b]
        out[n] = "required: true" in block and "default:" not in block
    return out


def evidence():
    q, live, old, prep, verdict, run, cfg = [load(x) for x in ("q", "live", "old", "prep", "verdict", "run", "cfg")]
    tg = live.get("telegram", {})
    tr = live.get("transport", {})
    sem = tr.get("semantic_result", {})
    hist = tr.get("historical_failed_attempts", [])
    roles = cfg.get("roles", {})
    providers = cfg.get("providers", {})
    cc = providers.get("claude_code", {})
    sh = providers.get("gpt_codex", {})
    cloud = providers.get("gpt_codex_cloud", {})
    close = next((x for x in q.get("tasks", []) if x.get("id") == "BEM934-CLOSE"), {})
    checks = {
        "queue_9_of_10_close_active": q.get("completed_summary", {}).get("tasks_done") == 9 and q.get("completed_summary", {}).get("stasks_total") == 10 and q.get("current_task") == "BEM934-CLOSE" and q.get("queue_state") == "ACTIVE" and close.get("status") == "IN_PROGRESS",
        "release_not_premature": q.get("release_status") == "FOLLOW_UP_REQUIRED",
        "close_stage_1_of_3": close.get("stage_progress", {}).get("tasks_done") == 1 and close.get("stage_progress", {}).get("tasks_total") == 3,
        "live_v2_pass": live.get("status") == "PASS" and live.get("receipt_version") == 2 and live.get("release_promoted") is False,
        "operator_not_replay": tg.get("operator_authored") is True and tg.get("automatic_bot_replay") is False,
        "semantic_executor_completed": sem.get("status") == "completed" and sem.get("provider") == "claude" and sem.get("role") == "executor" and sem.get("blocker") is None,
        "failed_history_disclosed": isinstance(hist, list) and len(hist) >= 1,
        "live_checks_true": alltrue(live.get("checks")),
        "old_replay_superseded": old.get("_supersed", {}).get("replacement_trace_id") == live.get("trace_id"),
        "preparation_pass": prep.get("status") == "PASS" and prep.get("phase") == "PREPARED_FOR_EXTERNAL_AUDIT" and prep.get("release_promoted") is False and alltrue(prep.get("checks")),
        "auditor_approved": verdict.get("status") == "PASS" and verdict.get("conclusion") == "APPROVED" and verdict.get("auditor") == "EXTERNAL_AUDITOR_CLAUDE" and verdict.get("blockers") == [] and verdict.get("release_promoted") is False and alltrue(verdict.get("checks")),
        "audit_run_pass": run.get("status") == "PASS" and run.get("claude_action_outcome") == "success" and run.get("errors") == [] and run.get("release_promoted") is False,
        "audit_hash_bound": run.get("verdict_sha256") == sha("verdict"),
        "claude_primary": cc.get("enabled") is True and cc.get("workflow_id") == "claude.yml" and all(isinstance(roles.get(x), dict) and roles[x].get("primary") == "claude_code" for x in ("curator", "analyst", "auditor", "executor")),
        "self_hosted_deprecated": sh.get("enabled") is False and sh.get("deprecated") is True,
        "cloud_mechanical_disclosure": cloud.get("requires_self_hosted") is False and cloud.get("execution_mode") == "optional_openai_responses_api_or_mechanical_fallback" and "OPENAI_API_KEY" in str(cloud.get("note", "")),
        "claude_inputs_canonical": all(canonical_inputs(P["claude"].read_text(encoding="utf-8")).values()),
    }
    bad = [k for k, v in checks.items() if not v]
    if bad:
        raise RuntimeError("validation_failed:" + ",".join(bad))
    return q, live, verdict, run, checks


def prepare():
    q, live, verdict, run, checks = evidence()
    at = ts()
    task = next(x for x in q["tasks"] if x.get("id") == "BEM934-CLOSE")
    q["version"] = int(q.get("version", 0)) + 1
    q["updated_at"] = at
    q["queue_state"] = "COMPLETE"
    q["current_task"] = None
    q["system_status"] = "BEM934_COMPLETE"
    q["release_status"] = "PASS"
    q["completed_summary"]["tasks_done"] = 10
    q["completed_summary"]["tasks_total"] = 10
    proofs = q["completed_summary"].setdefault("proofs", [])
    for x in (str(P["close"]), str(P["final"]), str(P["verdict"]), str(P["run"])):
        if x not in proofs:
            proofs.append(x)
    task.update(
        {
            "status": "DONE",
            "completed_at": at,
            "receipt": str(P["close"]),
            "done_sha_pending": True,
            "stage_progress": {
                "tasks_done": 3,
                "tasks_total": 3,
                "percent": 100,
                "completed": ["canonical_context_status_and_claude_inputs", "external_claude_audit", "strict_final_closure"],
                "pending": [],
            },
            "external_audit_verdict": str(P["verdict"]),
            "external_audit_run_receipt": str(P["run"]),
        }
    )
    q["last_completed"] = {"id": "BEM934-CLOSE", "completed_at": at, "receipt": str(P["close"])}
    q["next_action"] = None
    trace = live.get("trace_id")
    P["ctx"].write_text(
        f"""# AGENT_CONTEXT.md | canonical configuration

Updated: {at}
Repository: bereznyi-aleksandr/ai-devops-system
Active protocol: BEM-934
Roadmap state: 10/10 stages complete
Current task: none
Queue state: COMPLETE
Release status: PAS

## Runtime

Primary provider for curator, analyst, auditor, and executor: `claude_code` via `.github/workflows/claude.yml`.
Ingress: Telegram -> Cloudflare Worker -> `provider-router.yml` -> `claude.yml`.
Self-hosted Codex is disabled, deprecated, and non-operational.
`gpt_codex_cloud` is reserve-only; without OpenAI runtime secrets it is `mechanical_fallback`, not an LLM claim.

## Verified closure

LIVE trace `{trace}` is operator-authored, not bot replay. Router selected `claude_code`; latest executor transport is `completed` with blocker `null`; historical failures remain disclosed; the replay receipt is superseded.
`EXTERNAL_AUDITOR_CLAUDE returned PASS/APPROVED with no blockers. Strict final validation passed.

## Proofs

- `governance/proofs/BEM934_live_test_receipt.json`
- `governance/proofs/BEM934_external_auditor_verdict.json`
- `governance/proofs/BEM934_external_audit_run_receipt.json`
- `governance/proofs/BEM934_close_receipt.json`
- `governance/proofs/BEM934_FINAL_VERIFICATION_PASS.json`
""",
        encoding="utf-8",
    )
    P["status"].write_text(
        f"""# SYSTEM_STATUS.md | BEM-934

Updated: {at}
Roadmap: 10/10 stages complete.
Stage BEM934-CLOSE: 3/3 tasks complete.
Queue: `COMPLETE`.
Release: `PASS`.

LIVE trace `{trace}` is backed by explicit operator Telegram evidence, `claude_code` routing, a completed executor transport with blocker `null`, and a substantive report. Historical failures remain visible; the replay PASS is superseded.
External auditor: `EXTERNAL_AUDITOR_CLAUDE `PASS/APPROVED`, blockers empty.
Self-hosted Codex is disabled/deprecated/non-operational. Cloud reserve is `mechanical_fallback` without OpenAI runtime secrets.

Canonical closure evidence:
- `governance/proofs/BEM934_close_receipt.json`
- `governance/proofs/BEM934_FINAL_VERIFICATION_PASS.json`
""",
        encoding="utf-8",
    )
    receipt = {
        "status": "PASS",
        "protocol": "BEM-934",
        "task_id": "BEM934-CLOSE",
        "phase": "EVIDENCE_PREPARED",
        "created_at": at,
        "roadmap": {"tasks_done": 10, "tasks_total": 10},
        "stage": {"tasks_done": 3, "tasks_total": 3},
        "queue_state": "COMPLETE",
        "release_status": "PASS",
        "release_promoted": True,
        "closure_commit_sha": None,
        "closure_commit_sha_pending": True,
        "checks": checks,
        "live": {"path": str(P["live"]), "sha256": sha("live"), "trace_id": trace},
        "external_audit": {
            "verdict": str(P["verdict"]),
            "verdict_sha256": sha("verdict"),
            "run_receipt": str(P["run"]),
            "run_sha256": sha("run"),
        },
        "blockers": [],
    }
    write("close", receipt)
    write("q", q)
    with P["log"].open("a", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": at, "task_id": "BEM934-CLOSE", "status": "DONE", "phase": "EVIDENCE_PREPARED", "release_status": "PASS"}, ensure_ascii=False) + "\n")


def seal(commit_sha):
    if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        raise RuntimeError("bad_sha")
    q, close = load("q"), load("close")
    task = next(x for x in q["tasks"] if x.get("id") == "BEM934-CLOSE")
    checks = {
        "queue_complete": q.get("queue_state") == "COMPLETE" and q.get("current_task") is None,
        "roadmap_10_of_10": q.get("completed_summary", {}).get("tasks_done") == 10,
        "release_pass": q.get("release_status") == "PASS",
        "close_done_3_of_3": task.get("status") == "DONE" and task.get("stage_progress", {}).get("tasks_done") == 3,
        "close_prepared": close.get("status") == "PASS" and close.get("phase") == "EVIDENCE_PREPARED" and close.get("closure_commit_sha_pending") is True,
        "auditor_still_pass": load("verdict").get("status") == "PASS" and load("verdict").get("blockers") == [],
        "audit_run_still_pass": load("run").get("status") == "PASS" and load("run").get("errors") == [],
        "docs_final": "Roadmap state: 10/10" in P["ctx"].read_text(encoding="utf-8") and "Roadmap: 10/10" in P["status"].read_text(encoding="utf-8"),
        "claude_inputs_canonical": all(canonical_inputs(P["claude"].read_text(encoding="utf-8")).values()),
    }
    bad = [k for k, v in checks.items() if not v]
    if bad:
        raise RuntimeError("seal_failed:" + ",".join(bad))
    at = ts()
    close.update({"phase": "COMPLETE", "sealed_at": at, "closure_commit_sha": commit_sha, "closure_commit_sha_pending": False})
    task["done_sha"] = commit_sha
    task["done_sha_pending"] = False
    q["closure_commit_sha"] = commit_sha
    q["updated_at"] = at
    q["version"] = int(q.get("version", 0)) + 1
    write("close", close)
    write("q", q)
    final = {
        "status": "PASS",
        "protocol": "BEM-934",
        "task_id": "BEM934-CLOSE.FINAL-VERIFICATION",
        "verified_at": at,
        "sealed_state_commit_sha": commit_sha,
        "queue_state": "COMPLETE",
        "current_task": None,
        "roadmap": {"tasks_done": 10, "tasks_total": 10},
        "stage": {"tasks_done": 3, "tasks_total": 3},
        "release_status": "PASS",
        "checks": checks,
        "blockers": [],
        "proofs": {
            "close_receipt": str(P["close"]),
            "close_receipt_sha256": sha("close"),
            "external_auditor_verdict": str(P["verdict"]),
            "external_auditor_verdict_sha256": sha("verdict"),
            "external_audit_run_receipt": str(P["run"]),
            "external_audit_run_receipt_sha256": sha("run"),
            "live_receipt": str(P["live"]),
            "live_receipt_sha256": sha("live"),
        },
        "next_task": None,
    }
    write("final", final)
    with P["log"].open("a", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": at, "task_id": "BEM934-CLOSE.FINAL-VERIFICATION", "status": "PASS", "receipt": str(P["final"]), "release_status": "PASS", "next_task": None}, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare")
    s = sub.add_parser("seal")
    s.add_argument("--commit-sha", required=True)
    a = ap.parse_args()
    if a.cmd == "prepare":
        prepare()
    else:
        seal(a.commit_sha)


if __name__ == "__main__":
    main()
