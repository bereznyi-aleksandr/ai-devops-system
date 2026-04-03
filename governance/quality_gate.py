from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Literal


SchemaVersion = Literal["v155"]
RoleName = Literal[
    "ANALYST",
    "AUDITOR",
    "CLOUD_CODE",
    "OPERATOR",
    "LEDGER_WRITER",
    "LEDGER_ROUTER",
    "NONE",
]
DecisionStatus = Literal["PASS", "FAIL", "REVIEW_REQUIRED"]


@dataclass
class QualityInput:
    schema_version: SchemaVersion
    actor_role: RoleName
    task_id: str
    event_id: str
    artifact_path: str
    proof_present: bool
    validation_passed: bool
    required_fields_present: bool
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class QualityDecision:
    schema_version: SchemaVersion
    component: str
    decision_type: str
    decision_status: DecisionStatus
    actor_role: RoleName
    task_id: str
    event_id: str
    artifact_path: str
    checks: Dict[str, bool]
    rationale: List[str]
    audit_role_replaced: bool
    policy_director_replaced: bool
    lifecycle_manager_replaced: bool
    recommended_next_step: str


class QualityGate:
    """
    Machine-readable quality evaluator.

    Important:
    - This component evaluates quality readiness only.
    - This component does NOT replace AUDITOR verdict authority.
    - This component does NOT replace Policy Director logic.
    - This component does NOT replace Lifecycle Manager transition authority.
    """

    COMPONENT_NAME = "quality_gate"
    SCHEMA_VERSION: SchemaVersion = "v155"

    ALLOWED_ROLES = {
        "ANALYST",
        "AUDITOR",
        "CLOUD_CODE",
        "OPERATOR",
        "LEDGER_WRITER",
        "LEDGER_ROUTER",
        "NONE",
    }

    def evaluate(self, quality_input: QualityInput) -> QualityDecision:
        rationale: List[str] = []

        checks = {
            "schema_version_valid": quality_input.schema_version == self.SCHEMA_VERSION,
            "actor_role_valid": quality_input.actor_role in self.ALLOWED_ROLES,
            "task_id_present": bool(quality_input.task_id),
            "event_id_present": bool(quality_input.event_id),
            "artifact_path_present": bool(quality_input.artifact_path),
            "proof_present": quality_input.proof_present,
            "validation_passed": quality_input.validation_passed,
            "required_fields_present": quality_input.required_fields_present,
        }

        if checks["schema_version_valid"]:
            rationale.append("schema_version is compatible with v155.")
        else:
            rationale.append("schema_version is incompatible with v155.")

        if checks["actor_role_valid"]:
            rationale.append("actor_role is inside canonical v155 role set.")
        else:
            rationale.append("actor_role is outside canonical v155 role set.")

        if checks["task_id_present"]:
            rationale.append("task_id is present.")
        else:
            rationale.append("task_id is missing.")

        if checks["event_id_present"]:
            rationale.append("event_id is present.")
        else:
            rationale.append("event_id is missing.")

        if checks["artifact_path_present"]:
            rationale.append("artifact_path is present.")
        else:
            rationale.append("artifact_path is missing.")

        if checks["proof_present"]:
            rationale.append("proof is present.")
        else:
            rationale.append("proof is absent.")

        if checks["validation_passed"]:
            rationale.append("validation checks passed.")
        else:
            rationale.append("validation checks failed.")

        if checks["required_fields_present"]:
            rationale.append("required fields are present.")
        else:
            rationale.append("required fields are missing.")

        if not all([
            checks["schema_version_valid"],
            checks["actor_role_valid"],
            checks["task_id_present"],
            checks["event_id_present"],
            checks["artifact_path_present"],
        ]):
            decision_status: DecisionStatus = "FAIL"
            rationale.append("Quality input contract is invalid.")
            next_step = "Correct quality input contract."
        elif checks["proof_present"] and checks["validation_passed"] and checks["required_fields_present"]:
            decision_status = "PASS"
            rationale.append("Quality gate passed for supplied artifact.")
            next_step = "Proceed within approved contour; final audit authority remains external."
        else:
            decision_status = "REVIEW_REQUIRED"
            rationale.append("Quality gate requires review due to missing proof or failed checks.")
            next_step = "Collect missing proof/checks and escalate if needed."

        return QualityDecision(
            schema_version=self.SCHEMA_VERSION,
            component=self.COMPONENT_NAME,
            decision_type="quality_evaluation",
            decision_status=decision_status,
            actor_role=quality_input.actor_role,
            task_id=quality_input.task_id,
            event_id=quality_input.event_id,
            artifact_path=quality_input.artifact_path,
            checks=checks,
            rationale=rationale,
            audit_role_replaced=False,
            policy_director_replaced=False,
            lifecycle_manager_replaced=False,
            recommended_next_step=next_step,
        )


def evaluate_quality(payload: Dict[str, Any]) -> Dict[str, Any]:
    required = {
        "schema_version",
        "actor_role",
        "task_id",
        "event_id",
        "artifact_path",
        "proof_present",
        "validation_passed",
        "required_fields_present",
    }
    missing = sorted(required - set(payload.keys()))
    if missing:
        raise ValueError(f"Missing required quality input fields: {missing}")

    quality_input = QualityInput(
        schema_version=payload["schema_version"],
        actor_role=payload["actor_role"],
        task_id=payload["task_id"],
        event_id=payload["event_id"],
        artifact_path=payload["artifact_path"],
        proof_present=bool(payload["proof_present"]),
        validation_passed=bool(payload["validation_passed"]),
        required_fields_present=bool(payload["required_fields_present"]),
        metadata=payload.get("metadata"),
    )
    decision = QualityGate().evaluate(quality_input)
    return asdict(decision)


if __name__ == "__main__":
    import sys

    raw = sys.stdin.read().strip()
    if not raw:
        example = {
            "schema_version": "v155",
            "actor_role": "CLOUD_CODE",
            "task_id": "TASK-P1-0002",
            "event_id": "TASK-P1-PROPOSED-0037",
            "artifact_path": "governance/quality_gate.py",
            "proof_present": True,
            "validation_passed": True,
            "required_fields_present": True,
            "metadata": {"step_name": "1.2"},
        }
        print(json.dumps(evaluate_quality(example), ensure_ascii=False, indent=2))
        sys.exit(0)

    payload = json.loads(raw)
    print(json.dumps(evaluate_quality(payload), ensure_ascii=False, indent=2))
