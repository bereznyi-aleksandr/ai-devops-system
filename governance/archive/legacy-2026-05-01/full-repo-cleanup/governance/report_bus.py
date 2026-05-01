from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Literal


SchemaVersion = Literal["v155"]
ReportStatus = Literal["ACCEPTED", "REJECTED", "NORMALIZED"]
ReportKind = Literal[
    "TASK_REPORT",
    "AUDIT_REPORT",
    "EXECUTION_REPORT",
    "OPERATOR_REPORT",
    "POLICY_REPORT",
]
RoleName = Literal[
    "ANALYST",
    "AUDITOR",
    "CLOUD_CODE",
    "OPERATOR",
    "LEDGER_WRITER",
    "LEDGER_ROUTER",
    "NONE",
]


@dataclass
class ReportInput:
    schema_version: SchemaVersion
    report_kind: ReportKind
    producer_role: RoleName
    task_id: str
    event_id: str
    payload: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ReportEnvelope:
    schema_version: SchemaVersion
    component: str
    envelope_type: str
    report_kind: ReportKind
    producer_role: RoleName
    task_id: str
    event_id: str
    normalized_payload: Dict[str, Any]
    checks: Dict[str, bool]
    policy_director_replaced: bool
    proof_ledger_replaced: bool
    rationale: List[str]


class ReportBus:
    """
    Machine-readable report transport / normalization component.

    Important:
    - This component does NOT make policy decisions.
    - This component does NOT replace Proof Ledger authority/storage.
    - This component only validates and normalizes report payloads.
    """

    COMPONENT_NAME = "report_bus"
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
        "TASK_REPORT",
        "AUDIT_REPORT",
        "EXECUTION_REPORT",
        "OPERATOR_REPORT",
        "POLICY_REPORT",
    }

    def normalize(self, report_input: ReportInput) -> ReportEnvelope:
        rationale: List[str] = []

        checks = {
            "schema_version_valid": report_input.schema_version == self.SCHEMA_VERSION,
            "report_kind_valid": report_input.report_kind in self.ALLOWED_KINDS,
            "producer_role_valid": report_input.producer_role in self.ALLOWED_ROLES,
            "task_id_present": bool(report_input.task_id),
            "event_id_present": bool(report_input.event_id),
            "payload_is_object": isinstance(report_input.payload, dict),
        }

        if checks["schema_version_valid"]:
            rationale.append("schema_version is compatible with v155.")
        else:
            rationale.append("schema_version is incompatible with v155.")

        if checks["report_kind_valid"]:
            rationale.append("report_kind is valid for report transport.")
        else:
            rationale.append("report_kind is invalid.")

        if checks["producer_role_valid"]:
            rationale.append("producer_role is inside canonical v155 role set.")
        else:
            rationale.append("producer_role is outside canonical v155 role set.")

        if checks["task_id_present"]:
            rationale.append("task_id is present.")
        else:
            rationale.append("task_id is missing.")

        if checks["event_id_present"]:
            rationale.append("event_id is present.")
        else:
            rationale.append("event_id is missing.")

        if checks["payload_is_object"]:
            rationale.append("payload is machine-readable object.")
        else:
            rationale.append("payload is not a machine-readable object.")

        normalized_payload = {
            "report_status": "NORMALIZED",
            "original_payload": report_input.payload,
            "metadata": report_input.metadata or {},
        }

        return ReportEnvelope(
            schema_version=self.SCHEMA_VERSION,
            component=self.COMPONENT_NAME,
            envelope_type="report_envelope",
            report_kind=report_input.report_kind,
            producer_role=report_input.producer_role,
            task_id=report_input.task_id,
            event_id=report_input.event_id,
            normalized_payload=normalized_payload,
            checks=checks,
            policy_director_replaced=False,
            proof_ledger_replaced=False,
            rationale=rationale,
        )


def normalize_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    required = {
        "schema_version",
        "report_kind",
        "producer_role",
        "task_id",
        "event_id",
        "payload",
    }
    missing = sorted(required - set(payload.keys()))
    if missing:
        raise ValueError(f"Missing required report input fields: {missing}")

    report_input = ReportInput(
        schema_version=payload["schema_version"],
        report_kind=payload["report_kind"],
        producer_role=payload["producer_role"],
        task_id=payload["task_id"],
        event_id=payload["event_id"],
        payload=payload["payload"],
        metadata=payload.get("metadata"),
    )
    envelope = ReportBus().normalize(report_input)
    return asdict(envelope)


if __name__ == "__main__":
    import sys

    raw = sys.stdin.read().strip()
    if not raw:
        example = {
            "schema_version": "v155",
            "report_kind": "TASK_REPORT",
            "producer_role": "ANALYST",
            "task_id": "TASK-P0-0025",
            "event_id": "TASK-P0-PROPOSED-0035",
            "payload": {
                "step_name": "P0.4",
                "status": "TASK_PROPOSED"
            },
            "metadata": {
                "source": "manual_example"
            }
        }
        print(json.dumps(normalize_report(example), ensure_ascii=False, indent=2))
        sys.exit(0)

    payload = json.loads(raw)
    print(json.dumps(normalize_report(payload), ensure_ascii=False, indent=2))
