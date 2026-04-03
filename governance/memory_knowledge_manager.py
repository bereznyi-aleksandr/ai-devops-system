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
KnowledgeKind = Literal[
    "TASK_MEMORY",
    "POLICY_KNOWLEDGE",
    "QUALITY_KNOWLEDGE",
    "LIFECYCLE_MEMORY",
    "OPERATOR_MEMORY",
    "GENERAL_KNOWLEDGE",
]
DecisionStatus = Literal["ACCEPTED", "REJECTED", "NORMALIZED"]


@dataclass
class MemoryKnowledgeInput:
    schema_version: SchemaVersion
    actor_role: RoleName
    task_id: str
    event_id: str
    knowledge_kind: KnowledgeKind
    key: str
    payload: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class MemoryKnowledgeRecord:
    schema_version: SchemaVersion
    component: str
    record_type: str
    decision_status: DecisionStatus
    actor_role: RoleName
    task_id: str
    event_id: str
    knowledge_kind: KnowledgeKind
    key: str
    normalized_payload: Dict[str, Any]
    checks: Dict[str, bool]
    rationale: List[str]
    audit_role_replaced: bool
    policy_director_replaced: bool
    lifecycle_manager_replaced: bool
    quality_gate_replaced: bool


class MemoryKnowledgeManager:
    """
    Machine-readable memory/knowledge normalization component.

    Important:
    - This component handles memory/knowledge normalization only.
    - This component does NOT replace AUDITOR verdict authority.
    - This component does NOT replace Policy Director logic.
    - This component does NOT replace Lifecycle Manager logic.
    - This component does NOT replace Quality Gate logic.
    """

    COMPONENT_NAME = "memory_knowledge_manager"
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

    ALLOWED_KINDS = {
        "TASK_MEMORY",
        "POLICY_KNOWLEDGE",
        "QUALITY_KNOWLEDGE",
        "LIFECYCLE_MEMORY",
        "OPERATOR_MEMORY",
        "GENERAL_KNOWLEDGE",
    }

    def normalize(self, mk_input: MemoryKnowledgeInput) -> MemoryKnowledgeRecord:
        rationale: List[str] = []

        checks = {
            "schema_version_valid": mk_input.schema_version == self.SCHEMA_VERSION,
            "actor_role_valid": mk_input.actor_role in self.ALLOWED_ROLES,
            "task_id_present": bool(mk_input.task_id),
            "event_id_present": bool(mk_input.event_id),
            "knowledge_kind_valid": mk_input.knowledge_kind in self.ALLOWED_KINDS,
            "key_present": bool(mk_input.key),
            "payload_is_object": isinstance(mk_input.payload, dict),
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

        if checks["knowledge_kind_valid"]:
            rationale.append("knowledge_kind is valid.")
        else:
            rationale.append("knowledge_kind is invalid.")

        if checks["key_present"]:
            rationale.append("key is present.")
        else:
            rationale.append("key is missing.")

        if checks["payload_is_object"]:
            rationale.append("payload is machine-readable object.")
        else:
            rationale.append("payload is not a machine-readable object.")

        status: DecisionStatus
        if all(checks.values()):
            status = "NORMALIZED"
            rationale.append("memory/knowledge payload normalized successfully.")
        else:
            status = "REJECTED"
            rationale.append("memory/knowledge payload failed normalization checks.")

        normalized_payload = {
            "knowledge_kind": mk_input.knowledge_kind,
            "key": mk_input.key,
            "payload": mk_input.payload,
            "metadata": mk_input.metadata or {},
        }

        return MemoryKnowledgeRecord(
            schema_version=self.SCHEMA_VERSION,
            component=self.COMPONENT_NAME,
            record_type="memory_knowledge_record",
            decision_status=status,
            actor_role=mk_input.actor_role,
            task_id=mk_input.task_id,
            event_id=mk_input.event_id,
            knowledge_kind=mk_input.knowledge_kind,
            key=mk_input.key,
            normalized_payload=normalized_payload,
            checks=checks,
            rationale=rationale,
            audit_role_replaced=False,
            policy_director_replaced=False,
            lifecycle_manager_replaced=False,
            quality_gate_replaced=False,
        )


def normalize_memory_knowledge(payload: Dict[str, Any]) -> Dict[str, Any]:
    required = {
        "schema_version",
        "actor_role",
        "task_id",
        "event_id",
        "knowledge_kind",
        "key",
        "payload",
    }
    missing = sorted(required - set(payload.keys()))
    if missing:
        raise ValueError(f"Missing required memory/knowledge input fields: {missing}")

    mk_input = MemoryKnowledgeInput(
        schema_version=payload["schema_version"],
        actor_role=payload["actor_role"],
        task_id=payload["task_id"],
        event_id=payload["event_id"],
        knowledge_kind=payload["knowledge_kind"],
        key=payload["key"],
        payload=payload["payload"],
        metadata=payload.get("metadata"),
    )
    record = MemoryKnowledgeManager().normalize(mk_input)
    return asdict(record)


if __name__ == "__main__":
    import sys

    raw = sys.stdin.read().strip()
    if not raw:
        example = {
            "schema_version": "v155",
            "actor_role": "ANALYST",
            "task_id": "TASK-P1-0003",
            "event_id": "TASK-P1-PROPOSED-0038",
            "knowledge_kind": "TASK_MEMORY",
            "key": "phase1.step1.3.example",
            "payload": {
                "summary": "Memory/Knowledge Manager prototype artifact",
                "status": "TASK_PROPOSED"
            },
            "metadata": {"step_name": "1.3"},
        }
        print(json.dumps(normalize_memory_knowledge(example), ensure_ascii=False, indent=2))
        sys.exit(0)

    payload = json.loads(raw)
    print(json.dumps(normalize_memory_knowledge(payload), ensure_ascii=False, indent=2))
