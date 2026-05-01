#!/usr/bin/env python3
from __future__ import annotations

from typing import Optional


class ArtifactClassifierError(RuntimeError):
    pass


def classify_path(path: str) -> str:
    p = (path or "").strip()

    if not p:
        raise ArtifactClassifierError("Empty artifact path")

    if p.startswith("governance/proposals/"):
        return "proposal"

    if p.startswith("governance/plans/"):
        return "plan"

    if p.startswith("governance/proofs/"):
        return "implementation_result"

    if p.startswith("governance/decisions/"):
        return classify_decision_path(p)

    raise ArtifactClassifierError(f"Unsupported artifact path: {path!r}")


def classify_decision_path(path: str) -> str:
    p = (path or "").strip()

    if "IMPLEMENTATION_COMPLETED-" in p:
        return "review_decision"

    if "/AUDIT-" in p:
        return "verification_decision"

    if "IMPLEMENTATION_PLAN-" in p:
        return "plan_decision"

    if "TASK_PROPOSED-" in p:
        return "task_decision"

    return "decision"


def classify_executor_result(
    produced_artifact_type: str,
    produced_artifact_path: str,
) -> str:
    t = (produced_artifact_type or "").strip().lower()
    p = (produced_artifact_path or "").strip()

    if t == "proposal":
        return "proposal"

    if t == "plan":
        return "plan"

    if t == "implementation result":
        return "implementation_result"

    if p:
        return classify_path(p)

    raise ArtifactClassifierError(
        f"Cannot classify EXECUTOR result: type={produced_artifact_type!r}, path={produced_artifact_path!r}"
    )


def classify_auditor_reviewed_ref(reviewed_ref: str) -> str:
    r = (reviewed_ref or "").strip()
    if not r:
        raise ArtifactClassifierError("Empty reviewed_ref")
    return classify_path(r)


def classify_any_ref(path: Optional[str]) -> str:
    p = (path or "").strip()
    if not p:
        raise ArtifactClassifierError("Empty artifact ref")
    return classify_path(p)
