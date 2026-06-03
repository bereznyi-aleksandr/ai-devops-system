#!/usr/bin/env python3
import json
from pathlib import Path

REQUIRED = ["gate", "receipt_type", "source", "captured_at_utc", "status", "evidence_ref", "commit_sha"]
RECEIPTS = [
    Path("governance/proofs/external/telegram/production_receipt
