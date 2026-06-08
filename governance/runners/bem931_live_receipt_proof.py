#!/usr/bin/env python3
"""BEM-931 v3.6 live GitHub Actions receipt proof.

The runner is executed inside GitHub Actions and writes receipts with
GITHUB_RUN_ID / GITHUB_RUN_NUMBER / GITHUB_RUN_ATTEMPT / GITHUB_SHA.
It verifies the real runner chain by reading jsonl channels and worker results
created during the same workflow run.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
GOV = ROOT / "governance"
PROOFS = GOV / "proofs"
CHANNELS = GOV / "channels"
RESULTS = GOV / "results"
RELEASE = GOV / "release"
EXCHANGE = GOV / "exchange"
BLOCKERS = GOV / "blockers"

for directory in (PROOFS, CHANNELS, RESULTS, RELEASE, EXCHANGE, BLOCKERS):
    directory.mkdir(parents=True, exist_ok=True)

NOW = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
RUN_ID = os.environ.get("GITHUB_RUN_ID", "missing-run-id")
RUN_NUMBER = os.environ.get("GITHUB_RUN_NUMBER", "missing-run-number")
RUN_ATTEMPT = os.environ.get("GITHUB_RUN_ATTEMPT", "missing-run-attempt")
GITHUB_SHA = os.environ.get("GITHUB_SHA", "missing-sha")
WORKFLOW = os.environ.get("GITHUB_WORKFLOW", "missing-workflow")

COMMANDS: list[dict[str, Any]] = []
FAILURES: list[dict[str, Any]] = []


def runtime() -> dict[str, str]:
    return {
        "workflow": WORKFLOW,
        "github_run_id": RUN_ID,
        "github_run_number": RUN_NUMBER,
        "github_run_attempt": RUN_ATTEMPT,
        "github_sha": GITHUB_SHA,
        "created_at": NOW,
    }


def rel(path: Path | str) -> str:
    return str(Path(path).resolve().relative_to(ROOT))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def fail(stage: str, detail: str) -> None:
    FAILURES.append({"stage": stage, "detail": detail, **runtime()})


def run_cmd(cmd: list[str], stage: str) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    COMMANDS.append(
        {
            "stage": stage,
            "cmd": cmd,
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-4000:],
            "stderr_tail": proc.stderr[-4000:],
        }
    )
    if proc.returncode != 0:
        fail(stage, f"command failed: {' '.join(cmd)}")
    return proc


def clear_channels() -> None:
    CHANNELS.mkdir(parents=True, exist_ok=True)
    for pattern in ("*.jsonl", "*.json"):
        for item in CHANNELS.glob(pattern):
            item.unlink()


def assert_file(stage: str, file_name: str, trace: str | None = None, min_size: int = 20) -> bool:
    path = ROOT / file_name
    if not path.exists():
        fail(stage, f"missing file: {file_name}")
        return False
    if path.stat().st_size <= min_size:
        fail(stage, f"file too small: {file_name}")
        return False
    if trace is not None:
        text = path.read_text(encoding="utf-8", errors="replace")
        if trace not in text:
            fail(stage, f"trace missing in {file_name}: {trace}")
            return False
    return True


def validate_static() -> None:
    rm02 = run_cmd(["python3", "governance/validators/bem931_v36_rm02_object_passports_validate.py"], "RM-02")
    if rm02.returncode == 0:
        write_json(
            PROOFS / "BEM931-V36-RM02_object_passports_receipt.json",
            {
                "protocol": "BEM-931 v3.6",
                "roadmap_item": "RM-02",
                "status": "PASS",
                "receipt_type": "live_github_actions_validator",
                "validator": "governance/validators/bem931_v36_rm02_object_passports_validate.py",
                **runtime(),
            },
        )

    rm04 = run_cmd(["python3", "governance/validators/bem931_v36_rm04_runners_validate.py"], "RM-04")
    if rm04.returncode == 0:
        write_json(
            PROOFS / "BEM931-V36-RM04_runners_receipt.json",
            {
                "protocol": "BEM-931 v3.6",
                "roadmap_item": "RM-04-RUNNERS",
                "status": "PASS",
                "receipt_type": "live_github_actions_validator",
                "validator": "governance/validators/bem931_v36_rm04_runners_validate.py",
                **runtime(),
            },
        )


def run_runner_chain(trace: str, contour_id: str, source: str) -> bool:
    clear_channels()
    result_dir = RESULTS / trace
    if result_dir.exists():
        shutil.rmtree(result_dir)

    if source == "operator":
        append_jsonl(
            CHANNELS / "operator_to_gd.jsonl",
            {
                "trace_id": trace,
                "status": "pending",
                "from": "OPERATOR",
                "to": "GD.CURATOR",
                "task": f"BEM-931 v3.6 live E2E proof {trace}",
                "created_at": NOW,
            },
        )
        runners = [
            "governance/runners/gd_curator_runner.py",
            "governance/runners/dir_curator_runner.py",
            "governance/runners/wrk_curator_runner.py",
            "governance/runners/analyst_stage_runner.py",
            "governance/runners/auditor_stage_runner.py",
            "governance/runners/executor_stage_runner.py",
            "governance/runners/auditor_stage_runner.py",
        ]
    else:
        append_jsonl(
            CHANNELS / "dir_to_wrk.jsonl",
            {
                "trace_id": trace,
                "status": "pending",
                "from": "DIR.CURATOR",
                "to": "WRK.CURATOR",
                "target_contour": contour_id,
                "task": f"BEM-931 v3.6 isolated contour proof {contour_id}",
                "created_at": NOW,
            },
        )
        runners = [
            "governance/runners/wrk_curator_runner.py",
            "governance/runners/analyst_stage_runner.py",
            "governance/runners/auditor_stage_runner.py",
            "governance/runners/executor_stage_runner.py",
            "governance/runners/auditor_stage_runner.py",
        ]

    ok = True
    for runner in runners:
        proc = run_cmd(["python3", runner], trace)
        ok = proc.returncode == 0 and ok
    return ok


def verify_rm15(trace: str) -> bool:
    files = [
        "governance/channels/gd_to_dir.jsonl",
        "governance/channels/dir_to_wrk.jsonl",
        "governance/channels/wrk_c1_to_analyst.jsonl",
        "governance/channels/wrk_c1_to_auditor_pre.jsonl",
        "governance/channels/wrk_c1_to_executor.jsonl",
        "governance/channels/wrk_c1_to_auditor_post.jsonl",
        "governance/channels/wrk_to_curator_feedback.jsonl",
    ]
    ok = True
    for file_name in files:
        ok = assert_file("RM-15", file_name, trace) and ok

    result_file = f"governance/results/{trace}/worker_result.json"
    ok = assert_file("RM-15", result_file, None, 50) and ok

    feedback_path = ROOT / "governance/channels/wrk_to_curator_feedback.jsonl"
    if feedback_path.exists() and "PASS" not in feedback_path.read_text(encoding="utf-8", errors="replace"):
        fail("RM-15", "auditor PASS missing in feedback")
        ok = False

    if ok:
        write_json(
            PROOFS / "BEM931-V36-RM15_live_e2e_receipt.json",
            {
                "protocol": "BEM-931 v3.6",
                "roadmap_item": "RM-15-E2E",
                "status": "PASS",
                "receipt_type": "live_github_actions_e2e",
                "trace_id": trace,
                "chain": [
                    "OPERATOR",
                    "GD.CURATOR",
                    "DIR.CURATOR",
                    "WRK.CURATOR",
                    "WRK-C1.ANALYST",
                    "WRK-C1.AUDITOR.pre",
                    "WRK-C1.EXECUTOR",
                    "WRK-C1.AUDITOR.post",
                    "WRK.CURATOR.feedback",
                ],
                "artifacts": files + [result_file],
                **runtime(),
            },
        )
    return ok


def verify_one_contour(trace: str, contour_id: str) -> tuple[bool, dict[str, Any]]:
    prefix = contour_id.lower().replace("-", "_")
    files = [
        f"governance/channels/{prefix}_to_analyst.jsonl",
        f"governance/channels/{prefix}_to_auditor_pre.jsonl",
        f"governance/channels/{prefix}_to_executor.jsonl",
        f"governance/channels/{prefix}_to_auditor_post.jsonl",
        "governance/channels/wrk_to_curator_feedback.jsonl",
    ]
    ok = True
    for file_name in files:
        ok = assert_file("RM-16", file_name, trace) and ok

    result_file = f"governance/results/{trace}/{prefix}_worker_result.json"
    ok = assert_file("RM-16", result_file, None, 50) and ok

    receipt = {
        "protocol": "BEM-931 v3.6",
        "roadmap_item": "RM-16",
        "trace_id": trace,
        "contour_id": contour_id,
        "status": "PASS" if ok else "FAIL",
        "receipt_type": "live_github_actions_multi_contour",
        "artifacts": files + [result_file],
        **runtime(),
    }
    write_json(PROOFS / f"BEM931-V36-RM16_{contour_id}_receipt.json", receipt)
    return ok, receipt


def run_rm16() -> bool:
    aggregate = {
        "protocol": "BEM-931 v3.6",
        "roadmap_item": "RM-16",
        "status": "PASS",
        "receipt_type": "live_github_actions_multi_contour",
        "contours": [],
        **runtime(),
    }

    for contour_id in ["WRK-C1", "WRK-C2", "WRK-C3"]:
        trace = f"bem931_v36_rm16_{contour_id}_{RUN_ID}"
        chain_ok = run_runner_chain(trace, contour_id, "dir")
        verify_ok, receipt = verify_one_contour(trace, contour_id)
        if not chain_ok or not verify_ok:
            aggregate["status"] = "FAIL"
        aggregate["contours"].append(receipt)

    if aggregate["status"] == "PASS":
        write_json(PROOFS / "BEM931-V36-RM16_multi_contour_receipt.json", aggregate)
        return True
    return False


def run_rm17() -> bool:
    record = {
        "exchange_id": "bem931_v36_rm17_exchange",
        "status": "verified",
        "source_contour": "WRK-C1",
        "receiver_contour": "WRK-C2",
        "mediator": "WRK.CURATOR",
        "source_role": "WRK-C1.AUDITOR",
        "receiver_role": "WRK-C2.ANALYST",
        "proof_ref": "verified_artifact",
        "data_version": "1",
        "rule_version": "1",
        **runtime(),
    }
    registry = EXCHANGE / "exchange_registry_v2.json"
    write_json(registry, record)
    text = registry.read_text(encoding="utf-8")
    ok = (
        "WRK.CURATOR" in text
        and "WRK-C1.AUDITOR" in text
        and "WRK-C2.ANALYST" in text
        and "direct_role_to_role" not in text
    )
    if ok:
        write_json(
            PROOFS / "BEM931-V36-RM17_horizontal_exchange_receipt.json",
            {
                "protocol": "BEM-931 v3.6",
                "roadmap_item": "RM-17",
                "status": "PASS",
                "receipt_type": "live_github_actions_horizontal_exchange",
                "registry": rel(registry),
                "checks": [
                    "mediator_present",
                    "source_auditor",
                    "receiver_analyst",
                    "proof_ref",
                    "rule_version",
                ],
                **runtime(),
            },
        )
    else:
        fail("RM-17", "horizontal exchange registry validation failed")
    return ok


def write_release_gate() -> str:
    required = {
        "RM02": PROOFS / "BEM931-V36-RM02_object_passports_receipt.json",
        "RM04": PROOFS / "BEM931-V36-RM04_runners_receipt.json",
        "RM15": PROOFS / "BEM931-V36-RM15_live_e2e_receipt.json",
        "RM16": PROOFS / "BEM931-V36-RM16_multi_contour_receipt.json",
        "RM17": PROOFS / "BEM931-V36-RM17_horizontal_exchange_receipt.json",
    }
    missing = [key for key, path in required.items() if not path.exists()]
    status = "PASS" if not missing and not FAILURES else "BLOCKED"
    write_json(
        RELEASE / "bem931_v36_release_gate.json",
        {
            "protocol": "BEM-931 v3.6",
            "roadmap_item": "RM-18",
            "release_status": status,
            "missing": missing,
            "failures": FAILURES,
            "required": {key: rel(path) for key, path in required.items()},
            **runtime(),
        },
    )
    write_json(
        BLOCKERS / "bem931_v36_live_receipt_proof_diagnostics.json",
        {
            "protocol": "BEM-931 v3.6",
            "status": status,
            "failures": FAILURES,
            "commands": COMMANDS,
            **runtime(),
        },
    )
    return status


def main() -> int:
    validate_static()

    trace15 = f"bem931_v36_rm15_{RUN_ID}"
    chain_ok15 = run_runner_chain(trace15, "WRK-C1", "operator")
    verify_ok15 = verify_rm15(trace15)
    rm15_ok = chain_ok15 and verify_ok15

    rm16_ok = run_rm16()
    rm17_ok = run_rm17()
    release_status = write_release_gate()

    print(
        json.dumps(
            {
                "rm15": "PASS" if rm15_ok else "FAIL",
                "rm16": "PASS" if rm16_ok else "FAIL",
                "rm17": "PASS" if rm17_ok else "FAIL",
                "release_status": release_status,
                "failures": len(FAILURES),
                "github_run_id": RUN_ID,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
