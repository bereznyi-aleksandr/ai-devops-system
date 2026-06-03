#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

REQUIRED=['trace_id','readiness_level','status','events']
FORBIDDEN_ACTIONS={'status','deterministic status action'}

def main()->int:
    path=Path('governance/state/OBJ-GD-001_last_
