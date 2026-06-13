#!/usr/bin/env python3
"""Experience loader for BEM-931/BEM-932 error -> experience -> rule cycle."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = ROOT / "governance" / "experience" / "experience_registry.json"
CYCLE_PATH = ROOT / "governance" / "experience" / "error_rule_cycle.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_experience(path: str | Path = DEFAULT_REGISTRY) -> Dict[str, Any]:
    """Load the experience registry and return a normalized dict."""
    registry_path = Path(path)
    if not registry_path.is_absolute():
        registry_path = ROOT  / registry_path

    data = _read_json(registry_path)
    records = data.get("records")
    if records is None:
        data["records"] = []
    elif isinstance(records, dict):
        data["records"] = list(records.values())
    elif not isinstance(records, list):
        raise ValueError("experience_registry.records must be a list or object")

    return data


def validate_record(record: Dict[str, Any], cycle_path: str | Path = CYCLE_PATH) -> None:
    """Validate mandatory fields defined by error_rule_cycle.json."""
    path = Path(cycle_path)
    if not path.is_absolute():
        path = ROOT  / path
    cycle = _read_json(path)
    mandatory = cycle.get(
        "mandatory_fields",
        ["error_id", "source", "classification", "proof_ref", "rule_version_before", "action", "status"],
    )
    missing = [field for field in mandatory if not record.get(field)]
    if missing:
        raise ValueError(f"experience record missing fields: {missing}")


def append_experience(record: Dict[str, Any], path: str | Path = DEFAULT_REGISTRY) -> Dict[str, Any]:
    """Append or replace an experience record by error_id and persist the registry."""
    validate_record(record)

    registry_path = Path(path)
    if not registry_path.is_absolute():
        registry_path = ROOT / registry_path

    data = load_experience(registry_path)
    data.setdefault("schema_version", "1.0")
    data.setdefault("protocol", "BEM-931 v3.5 / BEM-932")
    data.setdefault("records", [])
    data["updated_at"] = _utc_now()

    record = dict(record)
    record.setdefault("created_at", data["updated_at"])

    existing: List[Dict[str, Any]] = [r for r in data["records"] if r.get("error_id") != record.get("error_id")]
    existing.append(record)
    data["records"] = existing

    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Load or append BEM experience records")
    parser.add_argument("--append-test", action="store_true", help="Append a deterministic validation record")
    parser.add_argument("--path", default=str(DEFAULT_REGISTRY))
    args = parser.parse_args()

    if args.append_test:
        data = append_experience(
            {
                "error_id": "BEM932-EXPERIENCE-FIX-TEST",
                "source": "governance/runtime/experience_loader.py",
                "classification": "registry_repair_validation",
                "proof_ref": "governance/proofs/BEM932_experience_fix_receipt.json",
                "rule_version_before": "BEM-931 v3.5 RM-13 formal pass",
                "action": "restore valid experience registry and loader",
                "status": "validated",
            },
            args.path,
        )
    else:
        data = load_experience(args.path)

    print(json.dumps({"status": "PASS", "records": len(data.get("records", []))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
