import json
from pathlib import Path


def aggregate(report_paths):
    reports = []
    errors = []
    for path in report_paths:
        p = Path(path)
        if not p
