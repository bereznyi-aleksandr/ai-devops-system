import json

DEFAULT_ASSIGNMENT = {"mock_e2e": "C1", "validator_tests": "C2", "release_proof_tests": "C3"}


def assign(test_type):
    contour = DEFAULT_ASSIGNMENT
