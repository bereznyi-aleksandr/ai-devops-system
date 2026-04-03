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
LifecycleStatus = Literal[
    "TASK_PROPOSED",
    "PRE_ACTION_APPROVED",
    "PRE_ACTION_REJECTED",
    "ACTION_EXECUTION_REQUEST",
    "ACTION_COMPLETED",
    "POST_ACTION_APPROVED",
    "POST_ACTION_REJECTED",
    "TASK_CLOSED",
    "EMERGENCY_BLOCKED",
    "VALIDATION_FAILED",
]
DecisionStatus = Literal["ALLOW", "DENY", "REVIEW_REQUIRED"]


@dataclass
class LifecycleInput:
    schema_version: SchemaVersion
    current_status: LifecycleStatus
    requested_next_status: LifecycleStatus
    actor_role: RoleName
    task_id: str
    event_id: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class LifecycleDecision:
    schema_version: SchemaVersion
    component: str
    decision_type: str
    decision_status: DecisionStatus
    current_status: LifecycleStatus
    requested_next_status: LifecycleStatus
    actor_role: RoleName
    task_id: str
    event_id: str
    checks: Dict[str, bool]
    rationale: List[str]
    allowed_transition: bool
    audit_role_replaced: bool
    policy_director_replaced: bool
    recommended_next_step: str


class LifecycleManager:
    """
    Machine-readable lifecycle transition evaluator.

    Important:
    - This component evaluates lifecycle transitions only.
    - This component does NOT replace AUDITOR verdict authority.
    - This component does NOT replace Policy Director logic.
    """

    COMPONENT_NAME = "lifecycle_manager"
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

    ALLOWED_TRANSITIONS = {
        "TASK_PROPOSED": {"PRE_ACTION_APPROVED", "PRE_ACTION_REJECTED", "VALIDATION_FAILED"},
        "PRE_ACTION_APPROVED": {"ACTION_EXECUTION_REQUEST", "VALIDATION_FAILED", "EMERGENCY_BLOCKED"},
        "PRE_ACTION_REJECTED": {"TASK_PROPOSED", "TASK_CLOSED"},
        "ACTION_EXECUTION_REQUEST": {"ACTION_COMPLETED", "VALIDATION_FAILED", "EMERGENCY_BLOCKED"},
        "ACTION_COMPLETED": {"POST_ACTION_APPROVED", "POST_ACTION_REJECTED", "VALIDATION_FAILED"},
        "POST_ACTION_APPROVED": {"TASK_CLOSED", "TASK_PROPOSED"},
        "POST_ACTION_REJECTED": {"TASK_PROPOSED", "EMERGENCY_BLOCKED"},
        "TASK_CLOSED": set(),
        "EMERGENCY_BLOCKED": {"TASK_PROPOSED", "TASK_CLOSED"},
        "VALIDATION_FAILED": {"TASK_PROPOSED", "TASK_CLOSED"},
    }

    def evaluate(self, lifecycle_input: LifecycleInput) -> LifecycleDecision:
        rationale: List[str] = []

        schema_version_valid = lifecycle_input.schema_version == self.SCHEMA_VERSION
        actor_role_valid = lifecycle_input.actor_role in self.ALLOWED_ROLES
        task_id_present = bool(lifecycle_input.task_id)
        event_id_present = bool(lifecycle_input.event_id)
        current_known = lifecycle_input.current_status in self.ALLOWED_TRANSITIONS
        requested_known = any(
            lifecycle_input.requested_next_status == s
            for states in self.ALLOWED_TRANSITIONS.values()
            for s in states
        ) or lifecycle_input.requested_next_status in self.ALLOWED_TRANSITIONS

        allowed_transition = (
            current_known and
            lifecycle_input.requested_next_status in self.ALLOWED_TRANSITIONS[lifecycle_input.current_status]
        )

        checks = {
            "schema_version_valid": schema_version_valid,
            "actor_role_valid": actor_role_valid,
            "task_id_present": task_id_present,
            "event_id_present": event_id_present,
            "current_status_known": current_known,
            "requested_status_known": requested_known,
            "allowed_transition": allowed_transition,
        }

        if schema_version_valid:
            rationale.append("schema_version is compatible with v155.")
        else:
            rationale.append("schema_version is incompatible with v155.")

        if actor_role_valid:
            rationale.append("actor_role is inside canonical v155 role set.")
        else:
            rationale.append("actor_role is outside canonical v155 role set.")

        if task_id_present:
            rationale.append("task_id is present.")
        else:
            rationale.append("task_id is missing.")

        if event_id_present:
            rationale.append("event_id is present.")
        else:
            rationale.append("event_id is missing.")

        if current_known:
            rationale.append("current_status is known to lifecycle model.")
        else:
            rationale.append("current_status is unknown to lifecycle model.")

        if requested_known:
            rationale.append("requested_next_status is known to lifecycle model.")
        else:
            rationale.append("requested_next_status is unknown to lifecycle model.")

        if not schema_version_valid or not actor_role_valid or not task_id_present or not event_id_present:
            decision_status: DecisionStatus = "DENY"
            rationale.append("Lifecycle input contract is invalid.")
            next_step = "Correct lifecycle input contract."
        elif not allowed_transition:
            decision_status = "REVIEW_REQUIRED"
            rationale.append("Requested transition is not allowed by lifecycle model.")
            next_step = "Review transition and escalate to AUDITOR if needed."
        else:
            decision_status = "ALLOW"
            rationale.append("Requested transition is allowed by lifecycle model.")
            next_step = "Proceed within approved contour; verdict authority remains external."

        return LifecycleDecision(
            schema_version=self.SCHEMA_VERSION,
            component=self.COMPONENT_NAME,
            decision_type="lifecycle_transition_evaluation",
            decision_status=decision_status,
            current_status=lifecycle_input.current_status,
            requested_next_status=lifecycle_input.requested_next_status,
            actor_role=lifecycle_input.actor_role,
            task_id=lifecycle_input.task_id,
            event_id=lifecycle_input.event_id,
            checks=checks,
            rationale=rationale,
            allowed_transition=allowed_transition,
            audit_role_replaced=False,
            policy_director_replaced=False,
            recommended_next_step=next_step,
        )


def evaluate_lifecycle(payload: Dict[str, Any]) -> Dict[str, Any]:
    required = {
        "schema_version",
        "current_status",
        "requested_next_status",
        "actor_role",
        "task_id",
        "event_id",
    }
    missing = sorted(required - set(payload.keys()))
    if missing:
        raise ValueError(f"Missing required lifecycle input fields: {missing}")

    lifecycle_input = LifecycleInput(
        schema_version=payload["schema_version"],
        current_status=payload["current_status"],
        requested_next_status=payload["requested_next_status"],
        actor_role=payload["actor_role"],
        task_id=payload["task_id"],
        event_id=payload["event_id"],
        metadata=payload.get("metadata"),
    )
    decision = LifecycleManager().evaluate(lifecycle_input)
    return asdict(decision)


if __name__ == "__main__":
    import sys

    raw = sys.stdin.read().strip()
    if not raw:
        example = {
            "schema_version": "v155",
            "current_status": "TASK_PROPOSED",
            "requested_next_status": "PRE_ACTION_APPROVED",
            "actor_role": "AUDITOR",
            "task_id": "TASK-P1-0001",
            "event_id": "TASK-P1-PROPOSED-0036",
            "metadata": {"step_name": "1.1"},
        }
        print(json.dumps(evaluate_lifecycle(example), ensure_ascii=False, indent=2))
        sys.exit(0)

    payload = json.loads(raw)
    print(json.dumps(evaluate_lifecycle(payload), ensure_ascii=False, indent=2))
