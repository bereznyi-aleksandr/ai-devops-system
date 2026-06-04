#!/usr/bin/env python3
import json
from pathlib import Path

SCAN_DIRS = [Path("governance/proofs/external"), Path("governance/state")]

def main() -> int:
    violations = []
    for base in SCAN_DIRS:
        if not base
