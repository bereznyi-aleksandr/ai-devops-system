import json
from pathlib import Path


def write_report(output_path, report):
    required = {"bem_id", "role", "status", "summary", "proof"}
    missing = sorted(required -
