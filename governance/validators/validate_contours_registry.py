import json
from pathlib import Path

REQUIRED = {"id", "name", "director", "curator", "roles", "algorithm", "horizontal_outbound"}
EXPECTED_ALGORITHM = ["analyst_proposal", "auditor_precheck", "worker_execution", "auditor_postcheck"]


def validate(path="governance/contours/contours_registry
