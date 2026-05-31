import json
from pathlib import Path

REQUIRED_KEYS = {"audit_id", "auditor", "timestamp_utc3", "audited_evidence_refs", "decision", "findings", "blockers", "proof_ref"}
ALLOWED_DECISIONS = {"APPROVED", "PASS", "CONDITIONAL", "FAIL", "BLOCKED"}
FORBIDDEN_GPT_APPROVAL_DECISIONS = {"APPROVED", "PASS"}


def validate_audit_result(payload):
    errors = []
    missing = sorted(REQUIRED_KEYS -
