"""Autonomy governance constants.

U-01: deterministic tie-break rule.
Higher number wins. Sort descending. SYSTEM > AUDITOR > EXECUTOR.

U-02: terminal timeout is a named constant.
"""

ROLE_PRIORITY = {"SYSTEM": 3, "AUDITOR": 2, "EXECUTOR": 1}
TERMINAL_TIMEOUT_MINUTES = 15

def role_priority(role: str) -> int:
    return ROLE_PRIORITY.get(str(role).upper(), 0)

def sort_roles_by_priority_desc(roles):
    return sorted(roles, key=role_priority, reverse=True)
