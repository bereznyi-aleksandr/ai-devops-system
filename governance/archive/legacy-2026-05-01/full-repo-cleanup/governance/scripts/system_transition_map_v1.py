#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "governance" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "governance" / "scripts"))

from system_artifact_classifier_v1 import (  # noqa: E402
    classify_auditor_reviewed_ref,
    classify_executor_result,
)


class TransitionMapError(RuntimeError):
    pass


SUCCESS_TRANSITIONS: Dict[Tuple[str, str], Tuple[str, str, str, str]] = {
    # role, artifact_class -> (event_type, new_state, next_role, next_action)

    ("EXECUTOR", "proposal"): (
        "TASK_PROPOSED",
        "AUDIT_PENDING",
        "AUDITOR",
        "REVIEW_TASK",
    ),
    ("AUDITOR", "proposal"): (
        "AUDIT_DECISION",
        "APPROVED",
        "EXECUTOR",
        "WRITE_PLAN",
    ),

    ("EXECUTOR", "plan"): (
        "IMPLEMENTATION_PLAN",
        "PLAN_PENDING",
        "AUDITOR",
        "REVIEW_PLAN",
    ),
    ("AUDITOR", "plan"): (
        "PLAN_DECISION",
        "PLAN_APPROVED",
        "EXECUTOR",
        "IMPLEMENT_TASK",
    ),

    ("EXECUTOR", "implementation_result"): (
        "IMPLEMENTATION_COMPLETED",
        "REVIEW_PENDING",
        "AUDITOR",
        "REVIEW_CODE",
    ),
    ("AUDITOR", "implementation_result"): (
        "RESULT_REVIEW_CONFIRMED",
        "VERIFY_PENDING",
        "AUDITOR",
        "VERIFY_RESULT",
    ),

    ("AUDITOR", "review_decision"): (
        "RESULT_VERIFIED",
        "COMPLETED",
        "SYSTEM",
        "CLOSE_TASK",
    ),

    ("AUDITOR", "verification_decision"): (
        "RESULT_VERIFIED",
        "COMPLETED",
        "SYSTEM",
        "CLOSE_TASK",
    ),
}


def resolve_success_transition(role: str, result_data: dict) -> Tuple[str, str, str, str]:
    role = (role or "").strip().upper()

    if role == "EXECUTOR":
        artifact_class = classify_executor_result(
            result_data.get("produced_artifact_type", ""),
            result_data.get("produced_artifact_path", ""),
        )
    elif role == "AUDITOR":
        artifact_class = classify_auditor_reviewed_ref(
            result_data.get("reviewed_ref", ""),
        )
    else:
        raise TransitionMapError(f"Unsupported role for transition lookup: {role!r}")

    key = (role, artifact_class)
    if key not in SUCCESS_TRANSITIONS:
        raise TransitionMapError(f"Missing success transition for key={key!r}")

    return SUCCESS_TRANSITIONS[key]
