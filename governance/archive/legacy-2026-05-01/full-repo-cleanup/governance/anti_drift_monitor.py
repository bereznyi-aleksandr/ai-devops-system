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
DecisionStatus = Literal["NO_DRIFT", "DRIFT_DETECTED", "REVIEW_REQUIRED"]


@dataclass
class DriftInput:
    schema_version: SchemaVersion
    actor_role: RoleName
    task_id: str
    event_id: str
    expected_baseline: Dict[str, Any]
    observed_state: Dict[str, Any]
    scope_name: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class DriftDecision:
    schema_version: SchemaVersion
    component: str
    decision_type: str
    decision_status: DecisionStatus
    actor_role: RoleName
    task_id: str
    event_id: str
    scope_name: str
    drift_items: List[Dict[str, Any]]
    checks: Dict[str, bool]
    rationale: List[str]
    audit_role_replaced: bool
    policy_director_replaced: bool
    lifecycle_manager_replaced: bool
    quality_gate_replaced: bool
    memory_knowledge_manager_replaced: bool
    recommended_next_step: str


class AntiDriftMonitor:
    """
    Machine-readable drift evaluation component.

    Important:
    - This component evaluates drift only.
    - This component does NOT replace AUDITOR verdict authority.
    - This component does NOT replace Policy Director logic.
    - This component does NOT replace Lifecycle Manager logic.
    - This component does NOT replace Quality Gate logic.
    - This component does NOT replace Memory/Knowledge Manager logic.
    """

    COMPONENT_NAME = "anti_drift_monitor"
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

    def evaluate(self, drift_input: DriftInput) -> DriftDecision:
        rationale: List[str] = []

        checks = {
            "schema_version_valid": drift_input.schema_version == self.SCHEMA_VERSION,
            "actor_role_valid": drift_input.actor_role in self.ALLOWED_ROLES,
            "task_id_present": bool(drift_input.task_id),
            "event_id_present": bool(drift_input.event_id),
            "scope_name_present": bool(drift_input.scope_name),
            "expected_baseline_is_object": isinstance(drift_input.expected_baseline, dict),
            "observed_state_is_object": isinstance(drift_input.observed_state, dict),
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

        if checks["scope_name_present"]:
            rationale.append("scope_name is present.")
        else:
            rationale.append("scope_name is missing.")

        if checks["expected_baseline_is_object"]:
            rationale.append("expected_baseline is machine-readable object.")
        else:
            rationale.append("expected_baseline is not a machine-readable object.")

        if checks["observed_state_is_object"]:
            rationale.append("observed_state is machine-readable object.")
        else:
            rationale.append("observed_state is not a machine-readable object.")

        drift_items: List[Dict[str, Any]] = []

        if checks["expected_baseline_is_object"] and checks["observed_state_is_object"]:
            expected_keys = set(drift_input.expected_baseline.keys())
            observed_keys = set(drift_input.observed_state.keys())
            all_keys = sorted(expected_keys | observed_keys)

            for key in all_keys:
                expected_value = drift_input.expected_baseline.get(key, "__MISSING__")
                observed_value = drift_input.observed_state.get(key, "__MISSING__")
                if expected_value != observed_value:
                    drift_items.append(
                        {
                            "field": key,
                            "expected": expected_value,
                            "observed": observed_value,
                        }
                    )

        if not all(checks.values()):
            status: DecisionStatus = "REVIEW_REQUIRED"
            rationale.append("Input contract invalid or incomplete for drift evaluation.")
            next_step = "Correct drift input contract."
        elif drift_items:
            status = "DRIFT_DETECTED"
            rationale.append("Observed state diverges from expected baseline.")
            next_step = "Review drift and escalate if needed."
        else:
            status = "NO_DRIFT"
            rationale.append("Observed state matches expected baseline.")
            next_step = "Proceed within approved contour; final authority remains external."

        return DriftDecision(
            schema_version=self.SCHEMA_VERSION,
            component=self.COMPONENT_NAME,
            decision_type="drift_evaluation",
            decision_status=status,
            actor_role=drift_input.actor_role,
            task_id=drift_input.task_id,
            event_id=drift_input.event_id,
            scope_name=drift_input.scope_name,
            drift_items=drift_items,
            checks=checks,
            rationale=rationale,
            audit_role_replaced=False,
            policy_director_replaced=False,
            lifecycle_manager_replaced=False,
            quality_gate_replaced=False,
            memory_knowledge_manager_replaced=False,
            recommended_next_step=next_step,
        )


def evaluate_drift(payload: Dict[str, Any]) -> Dict[str, Any]:
    required = {
        "schema_version",
        "actor_role",
        "task_id",
        "event_id",
        "expected_baseline",
        "observed_state",
        "scope_name",
    }
    missing = sorted(required - set(payload.keys()))
    if missing:
        raise ValueError(f"Missing required drift input fields: {missing}")

    drift_input = DriftInput(
        schema_version=payload["schema_version"],
        actor_role=payload["actor_role"],
        task_id=payload["task_id"],
        event_id=payload["event_id"],
        expected_baseline=payload["expected_baseline"],
        observed_state=payload["observed_state"],
        scope_name=payload["scope_name"],
        metadata=payload.get("metadata"),
    )
    decision = AntiDriftMonitor().evaluate(drift_input)
    return asdict(decision)


if __name__ == "__main__":
    import sys

    raw = sys.stdin.read().strip()
    if not raw:
        example = {
            "schema_version": "v155",
            "actor_role": "ANALYST",
            "task_id": "TASK-P1-0004",
            "event_id": "TASK-P1-PROPOSED-0039",
            "expected_baseline": {"schema_version": "v155", "status": "READY"},
            "observed_state": {"schema_version": "v155", "status": "READY"},
            "scope_name": "phase1.step1.4.example",
            "metadata": {"step_name": "1.4"},
        }
        print(json.dumps(evaluate_drift(example), ensure_ascii=False, indent=2))
        sys.exit(0)

    payload = json.loads(raw)
    print(json.dumps(evaluate_drift(payload), ensure_ascii=False, indent=2))
