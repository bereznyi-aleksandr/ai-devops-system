import json
from pathlib import Path

EXPECTED = ["queued", "analyst_proposal", "auditor_precheck", "worker_execution", "auditor_postcheck", "completed", "blocked"]


def validate(path="governance/contours/contour_lifecycle_schema
