import json

ALLOWED = {
    "queued": ["analyst_proposal"],
    "analyst_proposal": ["auditor_precheck"],
    "auditor_precheck": ["worker_execution"],
    "worker_execution": ["auditor_postcheck"],
    "auditor_postcheck": ["completed"],
}


def advance(state, next_state, proof=None):
    current = state
