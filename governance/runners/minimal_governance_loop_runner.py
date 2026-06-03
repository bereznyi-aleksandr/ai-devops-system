#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

READINESS_LEVEL='FUNCTIONAL'
TRACE_ID='bem1284-minimal-local-e2e'

def event(step:int, role:str, status:str, payload:dict[str,Any])->dict[str,Any]:
    return {'step':step,'role':role,'status':status,'payload':payload}

def
