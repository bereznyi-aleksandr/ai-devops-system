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
ActivationResultType = Literal["AUTONOMY_ACTIVATED_DONE", "EXACT_RESIDUAL_OPERATOR_GATE_LOCALIZED"]


@dataclass
class AutonomyActivationInput:
    schema_version: SchemaVersion
    actor_role: RoleName
    task_id: str
    event_id: str
    next_step_id: str
    start_without_operator_handoff: bool
    routing_trace: List[RoleName]
    operator_used_as_postman: bool
    residual_operator_gate: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class AutonomyActivationDecision:
    schema_version: SchemaVersion
    component: str
    decision_type: str
    actor_role: RoleName
    task_id: str
    event_id: str
    next_step_id: str
    checks: Dict[str, bool]
    routing_trace: List[RoleName]
    start_without_operator_handoff: bool
    operator_used_as_postman: bool
    activation_result_type: ActivationResultType
    autonomy_activated: Optional[str]
    exact_residual_operator_gate: Optional[str]
    rationale: List[str]
    audit_role_replaced: bool
    policy_director_replaced: bool
    lifecycle_manager_replaced: bool
    quality_gate_replaced: bool
    memory_knowledge_manager_replaced: bool
    anti_drift_monitor_replaced: bool
    proof_full_autonomous_loop_replaced: bool
    agent_factory_step_replaced: bool


class AutonomyActivationRun:
    """
    Machine-readable live autonomy activation evaluator.

    Important:
    - This component evaluates live start without Operator handoff.
    - This component does NOT replace AUDITOR verdict authority.
    - This component does NOT replace existing governance components.
    """

    COMPONENT_NAME = "autonomy_activation_run"
    SCHEMA_VERSION: SchemaVersion = "v155"
    REQUIRED_ROUTING_TRACE = [
        "ANALYST",
        "AUDITOR",
        "CLOUD_CODE",
        "LEDGER_WRITER",
        "LEDGER_ROUTER",
    ]

    ALLOWED_ROLES = {
        "ANALYST",
        "AUDITOR",
        "CLOUD_CODE",
        "OPERATOR",
        "LEDGER_WRITER",
        "LEDGER_ROUTER",
        "NONE",
    }

    def evaluate(self, activation_input: AutonomyActivationInput) -> AutonomyActivationDecision:
        rationale: List[str] = []

        checks = {
            "schema_version_valid": activation_input.schema_version == self.SCHEMA_VERSION,
            "actor_role_valid": activation_input.actor_role in self.ALLOWED_ROLES,
            "task_id_present": bool(activation_input.task_id),
            "event_id_present": bool(activation_input.event_id),
            "next_step_id_present": bool(activation_input.next_step_id),
            "start_without_operator_handoff": activation_input.start_without_operator_handoff,
            "routing_trace_is_list": isinstance(activation_input.routing_trace, list),
            "routing_trace_non_empty": bool(activation_input.routing_trace),
            "operator_used_as_postman_flag_present": isinstance(activation_input.operator_used_as_postman, bool),
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

        if checks["next_step_id_present"]:
            rationale.append("next_step_id is present.")
        else:
            rationale.append("next_step_id is missing.")

        if checks["start_without_operator_handoff"]:
            rationale.append("Step started without manual Operator handoff.")
        else:
            rationale.append("Step did not start without manual Operator handoff.")

        if checks["routing_trace_is_list"] and checks["routing_trace_non_empty"]:
            rationale.append("routing trace is present.")
        else:
            rationale.append("routing trace is missing or invalid.")

        if activation_input.operator_used_as_postman:
            rationale.append("Operator was used as postman.")
        else:
            rationale.append("Operator was not used as postman.")

        routing_presence = {}
        for role in self.REQUIRED_ROUTING_TRACE:
            present = role in activation_input.routing_trace
            routing_presence[f"route_{role}_present"] = present
            if present:
                rationale.append(f"{role} is present in routing trace.")
            else:
                rationale.append(f"{role} is missing from routing trace.")

        checks.update(routing_presence)

        input_contract_ok = all([
            checks["schema_version_valid"],
            checks["actor_role_valid"],
            checks["task_id_present"],
            checks["event_id_present"],
            checks["next_step_id_present"],
            checks["routing_trace_is_list"],
            checks["routing_trace_non_empty"],
            checks["operator_used_as_postman_flag_present"],
        ])

        routing_ok = all(routing_presence.values())

        if not input_contract_ok:
            activation_result_type: ActivationResultType = "EXACT_RESIDUAL_OPERATOR_GATE_LOCALIZED"
            autonomy_activated = None
            exact_residual_operator_gate = "INPUT_CONTRACT_INCOMPLETE"
            rationale.append("Autonomy activation could not be proven due to incomplete input contract.")
        elif not checks["start_without_operator_handoff"]:
            activation_result_type = "EXACT_RESIDUAL_OPERATOR_GATE_LOCALIZED"
            autonomy_activated = None
            exact_residual_operator_gate = "MANUAL_OPERATOR_HANDOFF_REQUIRED"
            rationale.append("Autonomy activation failed because manual Operator handoff was still required.")
        elif not routing_ok:
            activation_result_type = "EXACT_RESIDUAL_OPERATOR_GATE_LOCALIZED"
            autonomy_activated = None
            exact_residual_operator_gate = "ROUTING_TRACE_INCOMPLETE"
            rationale.append("Autonomy activation failed because routing contour coverage is incomplete.")
        elif activation_input.operator_used_as_postman:
            activation_result_type = "EXACT_RESIDUAL_OPERATOR_GATE_LOCALIZED"
            autonomy_activated = None
            exact_residual_operator_gate = activation_input.residual_operator_gate or "OPERATOR_USED_AS_POSTMAN"
            rationale.append("Autonomy activation failed because Operator was still used as postman.")
        else:
            activation_result_type = "AUTONOMY_ACTIVATED_DONE"
            autonomy_activated = "DONE"
            exact_residual_operator_gate = None
            rationale.append("Live autonomy activation proven for next step without Operator handoff.")

        return AutonomyActivationDecision(
            schema_version=self.SCHEMA_VERSION,
            component=self.COMPONENT_NAME,
            decision_type="live_autonomy_activation_run",
            actor_role=activation_input.actor_role,
            task_id=activation_input.task_id,
            event_id=activation_input.event_id,
            next_step_id=activation_input.next_step_id,
            checks=checks,
            routing_trace=activation_input.routing_trace,
            start_without_operator_handoff=activation_input.start_without_operator_handoff,
            operator_used_as_postman=activation_input.operator_used_as_postman,
            activation_result_type=activation_result_type,
            autonomy_activated=autonomy_activated,
            exact_residual_operator_gate=exact_residual_operator_gate,
            rationale=rationale,
            audit_role_replaced=False,
            policy_director_replaced=False,
            lifecycle_manager_replaced=False,
            quality_gate_replaced=False,
            memory_knowledge_manager_replaced=False,
            anti_drift_monitor_replaced=False,
            proof_full_autonomous_loop_replaced=False,
            agent_factory_step_replaced=False,
        )


def evaluate_autonomy_activation(payload: Dict[str, Any]) -> Dict[str, Any]:
    required = {
        "schema_version",
        "actor_role",
        "task_id",
        "event_id",
        "next_step_id",
        "start_without_operator_handoff",
        "routing_trace",
        "operator_used_as_postman",
    }
    missing = sorted(required - set(payload.keys()))
    if missing:
        raise ValueError(f"Missing required autonomy activation input fields: {missing}")

    activation_input = AutonomyActivationInput(
        schema_version=payload["schema_version"],
        actor_role=payload["actor_role"],
        task_id=payload["task_id"],
        event_id=payload["event_id"],
        next_step_id=payload["next_step_id"],
        start_without_operator_handoff=bool(payload["start_without_operator_handoff"]),
        routing_trace=payload["routing_trace"],
        operator_used_as_postman=bool(payload["operator_used_as_postman"]),
        residual_operator_gate=payload.get("residual_operator_gate"),
        metadata=payload.get("metadata"),
    )
    decision = AutonomyActivationRun().evaluate(activation_input)
    return asdict(decision)


if __name__ == "__main__":
    import sys

    raw = sys.stdin.read().strip()
    if not raw:
        example = {
            "schema_version": "v155",
            "actor_role": "ANALYST",
            "task_id": "TASK-AUTO-0001",
            "event_id": "TASK-AUTO-PROPOSED-0042",
            "next_step_id": "NEXT_LIVE_STEP",
            "start_without_operator_handoff": True,
            "routing_trace": [
                "ANALYST",
                "AUDITOR",
                "CLOUD_CODE",
                "LEDGER_WRITER",
                "LEDGER_ROUTER"
            ],
            "operator_used_as_postman": False,
            "metadata": {"step_name": "AUTONOMY_ACTIVATION"},
        }
        print(json.dumps(evaluate_autonomy_activation(example), ensure_ascii=False, indent=2))
        sys.exit(0)

    payload = json.loads(raw)
    print(json.dumps(evaluate_autonomy_activation(payload), ensure_ascii=False, indent=2))
