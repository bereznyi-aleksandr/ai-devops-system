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
DecisionStatus = Literal["PROVEN", "NOT_PROVEN", "REVIEW_REQUIRED"]


@dataclass
class ProofLoopInput:
    schema_version: SchemaVersion
    actor_role: RoleName
    task_id: str
    event_id: str
    components: Dict[str, bool]
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ProofLoopDecision:
    schema_version: SchemaVersion
    component: str
    decision_type: str
    decision_status: DecisionStatus
    actor_role: RoleName
    task_id: str
    event_id: str
    loop_checks: Dict[str, bool]
    missing_components: List[str]
    rationale: List[str]
    audit_role_replaced: bool
    policy_director_replaced: bool
    lifecycle_manager_replaced: bool
    quality_gate_replaced: bool
    memory_knowledge_manager_replaced: bool
    anti_drift_monitor_replaced: bool
    recommended_next_step: str


class ProofFullAutonomousLoop:
    """
    Machine-readable full autonomous loop proof component.

    Important:
    - This component evaluates end-to-end loop coverage only.
    - This component does NOT replace AUDITOR verdict authority.
    - This component does NOT replace other governance components.
    """

    COMPONENT_NAME = "proof_full_autonomous_loop"
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

    REQUIRED_COMPONENTS = [
        "action_registry",
        "policy_director",
        "report_bus",
        "lifecycle_manager",
        "quality_gate",
        "memory_knowledge_manager",
        "anti_drift_monitor",
    ]

    def evaluate(self, proof_input: ProofLoopInput) -> ProofLoopDecision:
        rationale: List[str] = []

        loop_checks = {
            "schema_version_valid": proof_input.schema_version == self.SCHEMA_VERSION,
            "actor_role_valid": proof_input.actor_role in self.ALLOWED_ROLES,
            "task_id_present": bool(proof_input.task_id),
            "event_id_present": bool(proof_input.event_id),
            "components_is_object": isinstance(proof_input.components, dict),
        }

        if loop_checks["schema_version_valid"]:
            rationale.append("schema_version is compatible with v155.")
        else:
            rationale.append("schema_version is incompatible with v155.")

        if loop_checks["actor_role_valid"]:
            rationale.append("actor_role is inside canonical v155 role set.")
        else:
            rationale.append("actor_role is outside canonical v155 role set.")

        if loop_checks["task_id_present"]:
            rationale.append("task_id is present.")
        else:
            rationale.append("task_id is missing.")

        if loop_checks["event_id_present"]:
            rationale.append("event_id is present.")
        else:
            rationale.append("event_id is missing.")

        if loop_checks["components_is_object"]:
            rationale.append("components payload is machine-readable object.")
        else:
            rationale.append("components payload is not a machine-readable object.")

        missing_components: List[str] = []
        component_checks: Dict[str, bool] = {}

        if loop_checks["components_is_object"]:
            for name in self.REQUIRED_COMPONENTS:
                present = bool(proof_input.components.get(name, False))
                component_checks[f"component_{name}_present"] = present
                if present:
                    rationale.append(f"{name} is included in full autonomous loop proof.")
                else:
                    rationale.append(f"{name} is missing from full autonomous loop proof.")
                    missing_components.append(name)

        loop_checks.update(component_checks)

        if not all([
            loop_checks["schema_version_valid"],
            loop_checks["actor_role_valid"],
            loop_checks["task_id_present"],
            loop_checks["event_id_present"],
            loop_checks["components_is_object"],
        ]):
            status: DecisionStatus = "REVIEW_REQUIRED"
            rationale.append("Proof input contract invalid or incomplete.")
            next_step = "Correct proof input contract."
        elif missing_components:
            status = "NOT_PROVEN"
            rationale.append("Full autonomous loop is not proven because required components are missing.")
            next_step = "Complete missing loop coverage and re-run proof."
        else:
            status = "PROVEN"
            rationale.append("Full autonomous loop is proven across required governance components.")
            next_step = "Proceed within approved contour; final audit authority remains external."

        return ProofLoopDecision(
            schema_version=self.SCHEMA_VERSION,
            component=self.COMPONENT_NAME,
            decision_type="full_autonomous_loop_proof",
            decision_status=status,
            actor_role=proof_input.actor_role,
            task_id=proof_input.task_id,
            event_id=proof_input.event_id,
            loop_checks=loop_checks,
            missing_components=missing_components,
            rationale=rationale,
            audit_role_replaced=False,
            policy_director_replaced=False,
            lifecycle_manager_replaced=False,
            quality_gate_replaced=False,
            memory_knowledge_manager_replaced=False,
            anti_drift_monitor_replaced=False,
            recommended_next_step=next_step,
        )


def evaluate_full_autonomous_loop(payload: Dict[str, Any]) -> Dict[str, Any]:
    required = {
        "schema_version",
        "actor_role",
        "task_id",
        "event_id",
        "components",
    }
    missing = sorted(required - set(payload.keys()))
    if missing:
        raise ValueError(f"Missing required proof input fields: {missing}")

    proof_input = ProofLoopInput(
        schema_version=payload["schema_version"],
        actor_role=payload["actor_role"],
        task_id=payload["task_id"],
        event_id=payload["event_id"],
        components=payload["components"],
        metadata=payload.get("metadata"),
    )
    decision = ProofFullAutonomousLoop().evaluate(proof_input)
    return asdict(decision)


if __name__ == "__main__":
    import sys

    raw = sys.stdin.read().strip()
    if not raw:
        example = {
            "schema_version": "v155",
            "actor_role": "ANALYST",
            "task_id": "TASK-P1-0005",
            "event_id": "TASK-P1-PROPOSED-0040",
            "components": {
                "action_registry": True,
                "policy_director": True,
                "report_bus": True,
                "lifecycle_manager": True,
                "quality_gate": True,
                "memory_knowledge_manager": True,
                "anti_drift_monitor": True
            },
            "metadata": {"step_name": "1.5"},
        }
        print(json.dumps(evaluate_full_autonomous_loop(example), ensure_ascii=False, indent=2))
        sys.exit(0)

    payload = json.loads(raw)
    print(json.dumps(evaluate_full_autonomous_loop(payload), ensure_ascii=False, indent=2))
