#!/usr/bin/env python3
"""BEM-949 P6 auditable error-to-experience-to-rule dynamic refresh drill."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_INCIDENT_FIELDS = (
    "incident_id",
    "observed_at",
    "error_class",
    "rule_id",
    "source",
)


class LearningLoopError(ValueError):
    """Raised when an incident cannot produce a valid governed refresh."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LearningLoopError(f"json_object_required:{path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )


def required_text(value: dict[str, Any], key: str) -> str:
    field = value.get(key)
    if not isinstance(field, str) or not field.strip():
        raise LearningLoopError(f"missing_required_field:{key}")
    return field


def resolve_rule(
    incident: dict[str, Any],
    registry: dict[str, Any],
) -> dict[str, Any]:
    for key in REQUIRED_INCIDENT_FIELDS:
        if key == "source":
            if not isinstance(incident.get(key), dict):
                raise LearningLoopError("missing_required_object:source")
        else:
            required_text(incident, key)

    rules = registry.get("rules")
    if not isinstance(rules, list):
        raise LearningLoopError("registry_rules_not_list")

    rule_id = incident["rule_id"]
    matches = [
        entry
        for entry in rules
        if isinstance(entry, dict) and entry.get("id") == rule_id
    ]
    if len(matches) != 1:
        raise LearningLoopError(f"unknown_rule_id:{rule_id}")
    rule = matches[0]

    for key in ("id", "version", "owner", "scope"):
        required_text(rule, key)
    return rule


def run_negative_mapping_test(
    incident: dict[str, Any],
    registry: dict[str, Any],
) -> dict[str, Any]:
    candidate = copy.deepcopy(incident)
    candidate["rule_id"] = "RULE-999"
    expected = "unknown_rule_id:RULE-999"
    try:
        resolve_rule(candidate, registry)
    except LearningLoopError as error:
        observed = str(error)
        return {
            "mutation": "unknown_rule_mapping",
            "rejected": observed == expected,
            "observed_error": observed,
            "expected_error": expected,
        }
    return {
        "mutation": "unknown_rule_mapping",
        "rejected": False,
        "observed_error": None,
        "expected_error": expected,
    }


def build_receipt(
    incident_path: Path,
    registry_path: Path,
    refresh_path: Path,
    trace_id: str,
) -> dict[str, Any]:
    incident = read_json(incident_path)
    registry = read_json(registry_path)
    runner_path = Path(__file__).resolve()

    payload: dict[str, Any] = {
        "schema_version": 1,
        "protocol": "BEM-949",
        "task_id": "BEM949-P6-LEARNING-LOOP-DRILL",
        "receipt_id": "BEM949_p6_learning_loop",
        "created_at": utc_now(),
        "trace_id": trace_id,
        "evidence_kind": "runtime_execution",
        "runtime_execution_claim": True,
        "execution": {
            "executed_at": utc_now(),
            "runner_path": "governance/runners/bem949_learning_loop_drill.py",
            "runner_sha": sha256_file(runner_path),
            "runner_sha_type": "sha256_content",
            "incident_path": str(incident_path),
            "incident_sha": sha256_file(incident_path),
            "incident_sha_type": "sha256_content",
            "registry_path": str(registry_path),
            "registry_sha": sha256_file(registry_path),
            "registry_sha_type": "sha256_content",
        },
        "chain": {},
        "negative_validation": {},
        "blockers": [],
        "non_claim": (
            "This drill proves only the observed incident to experience to "
            "RULE-010 version refresh path. It does not claim a broad "
            "release result or autonomous policy mutation."
        ),
    }

    try:
        rule = resolve_rule(incident, registry)
        refresh = {
            "schema_version": 1,
            "protocol": "BEM-949",
            "task_id": "BEM949-P6-LEARNING-LOOP-DRILL",
            "refreshed_at": utc_now(),
            "trace_id": trace_id,
            "experience": {
                "experience_id": f"experience:{incident['incident_id']}",
                "incident_id": incident["incident_id"],
                "error_class": incident["error_class"],
                "source_kind": incident["source"]["kind"],
                "incident_sha": payload["execution"]["incident_sha"],
                "incident_sha_type": "sha256_content",
            },
            "rule": {
                "id": rule["id"],
                "version": rule["version"],
                "owner": rule["owner"],
                "scope": rule["scope"],
                "registry_sha": payload["execution"]["registry_sha"],
                "registry_sha_type": "sha256_content",
            },
            "dynamic_refresh": {
                "applied": True,
                "refresh_generation": 1,
                "refresh_basis": "current_canonical_rule_registry",
            },
        }
        write_json(refresh_path, refresh)
        persisted = read_json(refresh_path)
        refresh_readback = (
            persisted.get("rule", {}).get("id") == rule["id"]
            and persisted.get("rule", {}).get("version") == rule["version"]
            and persisted.get("experience", {}).get("incident_id")
            == incident["incident_id"]
        )
        negative = run_negative_mapping_test(incident, registry)
        payload["execution"]["refresh_path"] = str(refresh_path)
        payload["execution"]["refresh_sha"] = sha256_file(refresh_path)
        payload["execution"]["refresh_sha_type"] = "sha256_content"
        payload["chain"] = {
            "error": {
                "incident_id": incident["incident_id"],
                "error_class": incident["error_class"],
                "source": incident["source"],
            },
            "experience": refresh["experience"],
            "rule_version": refresh["rule"],
            "dynamic_refresh": {
                "refresh_readback_matches_current_rule": refresh_readback,
                **refresh["dynamic_refresh"],
            },
        }
        payload["negative_validation"] = negative
        accepted = refresh_readback and negative["rejected"]
        payload["acceptance"] = {
            "error_to_experience_recorded": True,
            "experience_to_rule_version_bound": True,
            "dynamic_refresh_readback": refresh_readback,
            "negative_unknown_rule_rejected": negative["rejected"],
        }
        payload["status"] = "PASS" if accepted else "BLOCKED"
        if not accepted:
            payload["blockers"].append("learning_loop_acceptance_not_met")
    except (OSError, json.JSONDecodeError, LearningLoopError, KeyError) as error:
        payload["status"] = "BLOCKED"
        payload["acceptance"] = {
            "error_to_experience_recorded": False,
            "experience_to_rule_version_bound": False,
            "dynamic_refresh_readback": False,
            "negative_unknown_rule_rejected": False,
        }
        payload["blockers"].append(
            f"learning_loop_error:{type(error).__name__}:{error}"
        )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--incident",
        default="governance/incidents/BEM949_p5a_utf8_decode_incident.json",
    )
    parser.add_argument(
        "--registry",
        default="governance/state/rule_registry.json",
    )
    parser.add_argument(
        "--refresh-out",
        default="governance/state/learning/BEM949_p6_dynamic_rule_refresh.json",
    )
    parser.add_argument(
        "--out",
        default="governance/proofs/BEM949_p6_learning_loop_receipt.json",
    )
    parser.add_argument("--trace-id", default="bem949_p6_learning_loop")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    receipt = build_receipt(
        Path(args.incident),
        Path(args.registry),
        Path(args.refresh_out),
        args.trace_id,
    )
    output_path = Path(args.out)
    write_json(output_path, receipt)
    print(json.dumps(receipt, ensure_ascii=True))
    return 0 if (not args.strict or receipt["status"] == "PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
