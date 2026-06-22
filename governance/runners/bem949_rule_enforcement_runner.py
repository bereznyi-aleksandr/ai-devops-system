#!/usr/bin/env python3
"""BEM-949 P5 runtime enforcement for RULE-004 through RULE-010."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TARGET_RULES = [f"RULE-{number:03d}" for number in range(4, 11)]
REQUIRED_FIELDS = (
    "id",
    "owner",
    "scope",
    "condition",
    "approved_action",
    "prohibited_action",
    "version",
)


class RuleValidationError(ValueError):
    """Raised when a governed rule registry fails enforcement."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuleValidationError("registry_not_object")
    return data


def validate_registry(registry: dict[str, Any]) -> dict[str, Any]:
    rules = registry.get("rules")
    if not isinstance(rules, list):
        raise RuleValidationError("rules_not_list")

    indexed: dict[str, list[dict[str, Any]]] = {rule_id: [] for rule_id in TARGET_RULES}
    for entry in rules:
        if not isinstance(entry, dict):
            continue
        rule_id = entry.get("id")
        if rule_id in indexed:
            indexed[rule_id].append(entry)

    checks: list[dict[str, Any]] = []
    for rule_id in TARGET_RULES:
        matches = indexed[rule_id]
        if len(matches) != 1:
            raise RuleValidationError(f"{rule_id}:expected_exactly_one_entry:{len(matches)}")
        entry = matches[0]
        for field in REQUIRED_FIELDS:
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                raise RuleValidationError(f"{rule_id}:missing_required_field:{field}")
        if entry["id"] != rule_id:
            raise RuleValidationError(f"{rule_id}:id_mismatch")
        checks.append(
            {
                "rule_id": rule_id,
                "owner": entry["owner"],
                "scope": entry["scope"],
                "version": entry["version"],
                "required_fields_present": True,
            }
        )

    return {"target_rules": TARGET_RULES, "checks": checks}


def negative_tests(registry: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for rule_id in TARGET_RULES:
        candidate = copy.deepcopy(registry)
        for entry in candidate["rules"]:
            if isinstance(entry, dict) and entry.get("id") == rule_id:
                entry.pop("prohibited_action", None)
                break
        try:
            validate_registry(candidate)
        except RuleValidationError as error:
            expected = f"{rule_id}:missing_required_field:prohibited_action"
            results.append(
                {
                    "rule_id": rule_id,
                    "mutation": "remove_prohibited_action",
                    "rejected": str(error) == expected,
                    "observed_error": str(error),
                    "expected_error": expected,
                }
            )
        else:
            results.append(
                {
                    "rule_id": rule_id,
                    "mutation": "remove_prohibited_action",
                    "rejected": False,
                    "observed_error": None,
                    "expected_error": f"{rule_id}:missing_required_field:prohibited_action",
                }
            )
    return results


def build_receipt(registry_path: Path, trace_id: str) -> dict[str, Any]:
    runner_path = Path(__file__).resolve()
    registry = load_json(registry_path)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "protocol": "BEM-949",
        "task_id": "BEM949-P5-RULE-ENFORCEMENT-COMPLETE",
        "receipt_id": "BEM949_p5_rule_enforcement_complete",
        "created_at": utc_now(),
        "trace_id": trace_id,
        "evidence_kind": "runtime_execution",
        "runtime_execution_claim": True,
        "execution": {
            "executed_at": utc_now(),
            "runner_path": "governance/runners/bem949_rule_enforcement_runner.py",
            "runner_sha": sha256_file(runner_path),
            "runner_sha_type": "sha256_content",
            "registry_path": str(registry_path),
            "registry_sha": sha256_file(registry_path),
            "registry_sha_type": "sha256_content",
        },
        "rules": {},
        "blockers": [],
        "non_claim": (
            "This receipt proves only the explicit RULE-004 through RULE-010 "
            "registry schema enforcement and mutation rejections executed here."
        ),
    }

    try:
        positive = validate_registry(registry)
        negative = negative_tests(registry)
        negative_passed = all(item["rejected"] for item in negative)
        payload["rules"] = {
            "positive_validation": positive,
            "negative_validation": negative,
        }
        payload["acceptance"] = {
            "positive_runtime_evidence": True,
            "negative_runtime_evidence": negative_passed,
            "all_target_rules_enforced": negative_passed,
        }
        payload["status"] = "PASS" if negative_passed else "BLOCKED"
        if not negative_passed:
            payload["blockers"].append("negative_mutation_not_rejected")
    except (OSError, json.JSONDecodeError, RuleValidationError) as error:
        payload["status"] = "BLOCKED"
        payload["acceptance"] = {
            "positive_runtime_evidence": False,
            "negative_runtime_evidence": False,
            "all_target_rules_enforced": False,
        }
        payload["blockers"].append(f"enforcement_error:{type(error).__name__}:{error}")

    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--registry",
        default="governance/state/rule_registry.json",
        help="Path to canonical rule registry.",
    )
    parser.add_argument(
        "--out",
        default="governance/proofs/BEM949_p5_rule_enforcement_complete_receipt.json",
        help="Receipt output path.",
    )
    parser.add_argument("--trace-id", default="bem949_p5_rule_enforcement")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    receipt = build_receipt(Path(args.registry), args.trace_id)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=True))
    return 0 if (not args.strict or receipt["status"] == "PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
