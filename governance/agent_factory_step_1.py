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
FinalResultType = Literal["PROVEN", "LOCALIZED"]


@dataclass
class AgentFactoryStepInput:
    schema_version: SchemaVersion
    actor_role: RoleName
    task_id: str
    event_id: str
    next_step_id: str
    machine_readable_start_payload_present: bool
    routing_trace: List[RoleName]
    operator_needed: bool
    residual_operator_gate: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class AgentFactoryStepDecision:
    schema_version: SchemaVersion
    component: str
    decision_type: str
    actor_role: RoleName
    task_id: str
    event_id: str
    next_step_id: str
    checks: Dict[str, bool]
    routing_trace: List[RoleName]
    operator_needed: bool
    autonomy_result_type: FinalResultType
    autonomous_loop_for_next_step: Optional[str]
    exact_residual_operator_gate: Optional[str]
    rationale: List[str]
    audit_role_replaced: bool
    policy_director_replaced: bool
    lifecycle_manager_replaced: bool
    quality_gate_replaced: bool
    memory_knowledge_manager_replaced: bool
    anti_drift_monitor_replaced: bool
    proof_full_autonomous_loop_replaced: bool


class AgentFactoryStep1:
    """
    Machine-readable first Agent Factory step with embedded autonomy proof-run.

    Important:
    - This component evaluates whether the next step can start without manual handoff.
    - This component does NOT replace AUDITOR verdict authority.
    - This component does NOT replace existing governance components.
    """

    COMPONENT_NAME = "agent_factory_step_1"
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

    def evaluate(self, step_input: AgentFactoryStepInput) -> AgentFactoryStepDecision:
        rationale: List[str] = []

        checks = {
            "schema_version_valid": step_input.schema_version == self.SCHEMA_VERSION,
            "actor_role_valid": step_input.actor_role in self.ALLOWED_ROLES,
            "task_id_present": bool(step_input.task_id),
            "event_id_present": bool(step_input.event_id),
            "next_step_id_present": bool(step_input.next_step_id),
            "machine_readable_start_payload_present": step_input.machine_readable_start_payload_present,
            "routing_trace_is_list": isinstance(step_input.routing_trace, list),
            "routing_trace_non_empty": bool(step_input.routing_trace),
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

        if checks["machine_readable_start_payload_present"]:
            rationale.append("machine-readable start payload is present.")
        else:
            rationale.append("machine-readable start payload is absent.")

        if checks["routing_trace_is_list"] and checks["routing_trace_non_empty"]:
            rationale.append("routing trace is present.")
        else:
            rationale.append("routing trace is missing or invalid.")

        routing_presence = {}
        for role in self.REQUIRED_ROUTING_TRACE:
            present = role in step_input.routing_trace
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
            checks["machine_readable_start_payload_present"],
            checks["routing_trace_is_list"],
            checks["routing_trace_non_empty"],
        ])

        routing_ok = all(routing_presence.values())

        if not input_contract_ok:
            autonomy_result_type: FinalResultType = "LOCALIZED"
            autonomous_loop_for_next_step = None
            exact_residual_operator_gate = "INPUT_CONTRACT_INCOMPLETE"
            rationale.append("Embedded autonomy proof-run failed due to incomplete input contract.")
        elif not routing_ok:
            autonomy_result_type = "LOCALIZED"
            autonomous_loop_for_next_step = None
            exact_residual_operator_gate = "ROUTING_TRACE_INCOMPLETE"
            rationale.append("Embedded autonomy proof-run failed due to incomplete routing contour coverage.")
        elif step_input.operator_needed:
            autonomy_result_type = "LOCALIZED"
            autonomous_loop_for_next_step = None
            exact_residual_operator_gate = step_input.residual_operator_gate or "UNSPECIFIED_OPERATOR_GATE"
            rationale.append("Operator involvement is still required and has been localized.")
        else:
            autonomy_result_type = "PROVEN"
            autonomous_loop_for_next_step = "PROVEN"
            exact_residual_operator_gate = None
            rationale.append("Next-step autonomous loop is proven without operator involvement.")

        return AgentFactoryStepDecision(
            schema_version=self.SCHEMA_VERSION,
            component=self.COMPONENT_NAME,
            decision_type="agent_factory_step_with_embedded_autonomy_proof",
            actor_role=step_input.actor_role,
            task_id=step_input.task_id,
            event_id=step_input.event_id,
            next_step_id=step_input.next_step_id,
            checks=checks,
            routing_trace=step_input.routing_trace,
            operator_needed=step_input.operator_needed,
            autonomy_result_type=autonomy_result_type,
            autonomous_loop_for_next_step=autonomous_loop_for_next_step,
            exact_residual_operator_gate=exact_residual_operator_gate,
            rationale=rationale,
            audit_role_replaced=False,
            policy_director_replaced=False,
            lifecycle_manager_replaced=False,
            quality_gate_replaced=False,
            memory_knowledge_manager_replaced=False,
            anti_drift_monitor_replaced=False,
            proof_full_autonomous_loop_replaced=False,
        )


def evaluate_agent_factory_step_1(payload: Dict[str, Any]) -> Dict[str, Any]:
    required = {
        "schema_version",
        "actor_role",
        "task_id",
        "event_id",
        "next_step_id",
        "machine_readable_start_payload_present",
        "routing_trace",
        "operator_needed",
    }
    missing = sorted(required - set(payload.keys()))
    if missing:
        raise ValueError(f"Missing required agent factory input fields: {missing}")

    step_input = AgentFactoryStepInput(
        schema_version=payload["schema_version"],
        actor_role=payload["actor_role"],
        task_id=payload["task_id"],
        event_id=payload["event_id"],
        next_step_id=payload["next_step_id"],
        machine_readable_start_payload_present=bool(payload["machine_readable_start_payload_present"]),
        routing_trace=payload["routing_trace"],
        operator_needed=bool(payload["operator_needed"]),
        residual_operator_gate=payload.get("residual_operator_gate"),
        metadata=payload.get("metadata"),
    )
    decision = AgentFactoryStep1().evaluate(step_input)
    return asdict(decision)


if __name__ == "__main__":
    import sys

    raw = sys.stdin.read().strip()
    if not raw:
        example = {
            "schema_version": "v155",
            "actor_role": "ANALYST",
            "task_id": "TASK-P2-0001",
            "event_id": "TASK-P2-PROPOSED-0041",
            "next_step_id": "PHASE2_NEXT_STEP",
            "machine_readable_start_payload_present": True,
            "routing_trace": [
                "ANALYST",
                "AUDITOR",
                "CLOUD_CODE",
                "LEDGER_WRITER",
                "LEDGER_ROUTER"
            ],
            "operator_needed": False,
            "metadata": {"step_name": "2.1"},
        }
        print(json.dumps(evaluate_agent_factory_step_1(example), ensure_ascii=False, indent=2))
        sys.exit(0)

    payload = json.loads(raw)
    print(json.dumps(evaluate_agent_factory_step_1(payload), ensure_ascii=False, indent=2))
