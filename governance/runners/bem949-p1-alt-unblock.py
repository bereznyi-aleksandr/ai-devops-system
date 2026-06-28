#!/usr/bin/env python3
"""Create static-only evidence for BEM-949 P1 workflow files.

This does not claim GitHub Actions run-level success.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
OUTPUT = ROOT / "governance" / "proofs" / "BEM949_p1_static_validation_receipt.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def write_receipt(receipt: dict) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def valid_workflow_document(document: object) -> tuple[bool, str | None]:
    if not isinstance(document, dict):
        return False, "top_level_not_mapping"
    # PyYAML 1.1 can decode the unquoted YAML key `on` as boolean True.
    trigger = document.get("on", document.get(True))
    if trigger is None:
        return False, "missing_on"
    jobs = document.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        return False, "missing_or_empty_jobs"
    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            return False, f"job_not_mapping:{job_name}"
        if "runs-on" not in job and "uses" not in job:
            return False, f"job_has_no_runner_or_reusable_workflow:{job_name}"
    return True, None


def main() -> int:
    try:
        import yaml
    except ImportError:
        write_receipt(
            {
                "schema_version": 1,
                "task_id": "BEM949-P1-ALT-UNBLOCK",
                "created_at": utc_now(),
                "status": "BLOCKED",
                "outcome": "static_validation_unavailable",
                "blocker": "PyYAML is unavailable; yaml.safe_load did not run",
                "broad_release_pass_claimed": False,
            }
        )
        print(json.dumps({"task_status": "BLOCKED", "receipt_path": str(OUTPUT.relative_to(ROOT))}))
        return 1

    files = sorted(WORKFLOWS.glob("bem949-p1-*.yml"))
    checks: list[dict] = []
    problems: list[dict] = []

    for path in files:
        raw = path.read_bytes()
        relative = str(path.relative_to(ROOT))
        try:
            document = yaml.safe_load(raw.decode("utf-8"))
            valid, reason = valid_workflow_document(document)
            if not valid:
                raise ValueError(reason)
            checks.append(
                {
                    "path": relative,
                    "git_blob_sha": git_blob_sha(raw),
                    "sha_type": "git_blob",
                    "yaml_safe_load": "PASS",
                    "static_schema": "PASS",
                }
            )
        except Exception as exc:
            problems.append({"path": relative, "error": f"{type(exc).__name___:{exc}"})

    if not files:
        problems.append(
            {
                "path": ".github/workflows/bem949-p1-*.yml",
                "error": "no_matching_workflows",
            }
        )

    passed = not problems
    receipt = {
        "schema_version": 1,
        "task_id": "BEM949-P1-ALT-UNBLOCK",
        "created_at": utc_now(),
        "status": "PASS" if passed else "BLOCKED",
        "outcome": "static_pass_only" if passed else "blocked_with_detail",
        "evidence_kind": "yaml_safe_load_static_validation",
        "scope": ".github/workflows/bem949-p1-*.yml",
        "checks": checks,
        "problems": problems,
        "limitations": [
            "Static validation does not prove GitHub Actions dispatch or run-level success.",
            "BEM949-P1-CI-STABILIZE remains independently blocked until run-level evidence exists.",
        ],
        "broad_release_pass_claimed": False,
    }
    write_receipt(receipt)
    print(
        json.dumps(
            {
                "task_status": "DONE_STATIC_ONLY" if passed else "BLOCKED",
                "receipt_path": str(OUTPUT.relative_to(ROOT)),
            }
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
