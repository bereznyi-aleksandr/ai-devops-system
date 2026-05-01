from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Literal


SchemaVersion = Literal["v155"]
DecisionStatus = Literal["ALLOW", "DENY", "REVIEW_REQUIRED"]
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
class PolicyInput:
    schema_version: SchemaVersion
    actor_role: RoleName
    action_id: str
    proof_present: bool
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    action_enabled: bool
    context: Optional[Dict[str, Any]] = None


@dataclass
class PolicyDecision:
    schema_version: SchemaVersion
    component: str
    decision_type: str
    decision_status: DecisionStatus
    actor_role: RoleName
    action_id: str
    rationale: List[str]
    checks: Dict[str, bool]
    requires_auditor_verdict: bool
    audit_role_replaced: bool
    recommended_next_step: str


class PolicyDirector:
    COMPONENT_NAME = "policy_director"
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

    def evaluate(self, policy_input: PolicyInput) -> PolicyDecision:
        rationale: List[str] = []
        checks = {
            "schema_version_valid": policy_input.schema_version == self.SCHEMA_VERSION,
            "actor_role_valid": policy_input.actor_role in self.ALLOWED_ROLES,
            "action_enabled": policy_input.action_enabled,
            "proof_present": policy_input.proof_present,
            "high_risk_requires_review": True,
        }

        if not checks["schema_version_valid"]:
            rationale.append("Invalid schema_version for policy evaluation.")
        else:
            rationale.append("schema_version is compatible with v155.")

        if not checks["actor_role_valid"]:
            rationale.append("actor_role is outside canonical v155 role set.")
        else:
            rationale.append("actor_role is inside canonical v155 role set.")

        if not checks["action_enabled"]:
            rationale.append("Action is disabled in registry.")
        else:
            rationale.append("Action is enabled in registry.")

        if policy_input.proof_present:
            rationale.append("Proof is present for the evaluated action/context.")
        else:
            rationale.append("Proof is absent for the evaluated action/context.")

        if not checks["schema_version_valid"] or not checks["actor_role_valid"]:
            status = "DENY"
            next_step = "Reject execution and correct contract/input."
        elif not checks["action_enabled"]:
            status = "DENY"
            next_step = "Do not proceed until action is enabled."
        elif policy_input.risk_level == "HIGH":
            status = "REVIEW_REQUIRED"
            rationale.append("High-risk action requires explicit Auditor review.")
            next_step = "Escalate to AUDITOR for verdict."
        elif not policy_input.proof_present:
            status = "REVIEW_REQUIRED"
            rationale.append("Missing proof requires Auditor review before acceptance.")
            next_step = "Collect proof and/or escalate to AUDITOR."
        else:
            status = "ALLOW"
            rationale.append("Policy checks pass; action is policy-allowable.")
            next_step = "Proceed within approved contour; final audit authority still external."

        return PolicyDecision(
            schema_version=self.SCHEMA_VERSION,
            component=self.COMPONENT_NAME,
            decision_type="policy_evaluation",
            decision_status=status,
            actor_role=policy_input.actor_role,
            action_id=policy_input.action_id,
            rationale=rationale,
            checks=checks,
            requires_auditor_verdict=(status != "ALLOW" or policy_input.risk_level != "LOW"),
            audit_role_replaced=False,
            recommended_next_step=next_step,
        )


def evaluate_policy(payload: Dict[str, Any]) -> Dict[str, Any]:
    required = {
        "schema_version",
        "actor_role",
        "action_id",
        "proof_present",
        "risk_level",
        "action_enabled",
    }
    missing = sorted(required - set(payload.keys()))
    if missing:
        raise ValueError(f"Missing required policy input fields: {missing}")

    policy_input = PolicyInput(
        schema_version=payload["schema_version"],
        actor_role=payload["actor_role"],
        action_id=payload["action_id"],
        proof_present=bool(payload["proof_present"]),
        risk_level=payload["risk_level"],
        action_enabled=bool(payload["action_enabled"]),
        context=payload.get("context"),
    )
    decision = PolicyDirector().evaluate(policy_input)
    return asdict(decision)


if __name__ == "__main__":
    import sys

    raw = sys.stdin.read().strip()
    if not raw:
        example = {
            "schema_version": "v155",
            "actor_role": "ANALYST",
            "action_id": "PROPOSE_TASK",
            "proof_present": True,
            "risk_level": "LOW",
            "action_enabled": True,
            "context": {"step_name": "P0.3"},
        }
        print(json.dumps(evaluate_policy(example), ensure_ascii=False, indent=2))
        sys.exit(0)

    payload = json.loads(raw)
    print(json.dumps(evaluate_policy(payload), ensure_ascii=False, indent=2))
