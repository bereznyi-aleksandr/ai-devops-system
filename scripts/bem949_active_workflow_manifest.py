#!/usr/bin/env python3
"""Build a BEM-949 manifest of active workflow dispatch interfaces."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / "governance" / "registry" / "BEM949_WORKFLOW_OPERABILITY_SCOPE.json"
OUT = ROOT / "governance" / "proofs" / "BEM949_p1_active_workflow_manifest.json"
REPORT = ROOT / "governance" / "reports" / "BEM949_p1_active_workflow_manifest.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def workflow_dispatch_inputs(path: Path) -> tuple[bool, list[dict[str, object]]]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    on_block = doc.get("on")
    if on_block is None:
        on_block = doc.get(True)
    if not isinstance(on_block, dict):
        return False, []
    dispatch = on_block.get("workflow_dispatch")
    if dispatch is None:
        return False, []
    if not isinstance(dispatch, dict):
        return True, []
    raw_inputs = dispatch.get("inputs", {})
    if not isinstance(raw_inputs, dict):
        return True, []
    inputs: list[dict[str, object]] = []
    for name, config in raw_inputs.items():
        config = config if isinstance(config, dict) else {}
        inputs.append(
            {
                "name": str(name),
                "required": bool(config.get("required", False)),
                "type": str(config.get("type", "string")),
                "has_default": "default" in config,
            }
        )
    return True, inputs


def main() -> int:
    scope = json.loads(SCOPE.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for item in scope["active_control_plane_workflows"]:
        relative_path = str(item["path"])
        workflow_path = ROOT / relative_path
        dispatch_available, inputs = workflow_dispatch_inputs(workflow_path)
        rows.append(
            {
                "path": relative_path,
                "purpose": item["purpose"],
                "provider": item["provider"],
                "static_validation": item["static_validation"],
                "workflow_dispatch_available": dispatch_available,
                "inputs": inputs,
                "required_input_count": sum(1 for value in inputs if value["required"]),
                "manual_dispatch_evidence": item["manual_dispatch_evidence"],
            }
        )

    payload = {
        "schema_version": 1,
        "protocol": "BEM-949",
        "task_id": "BEM949-P1-CI-STABILIZE",
        "receipt_id": "BEM949_p1_active_workflow_manifest",
        "created_at": utc_now(),
        "scope_registry": "governance/registry/BEM949_WORKFLOW_OPERABILITY_SCOPE.json",
        "workflow_count": len(rows),
        "workflows": rows,
        "checks": {
            "active_workflows_enumerated": bool(rows),
            "dispatch_interfaces_parsed": True,
            "all_active_workflows_static_valid_in_scope_registry": all(
                item["static_validation"] == "valid" for item in scope["active_control_plane_workflows"]
            ),
            "all_active_workflows_have_green_run_evidence": False,
        },
        "non_claim": (
            "This manifest inventories dispatch interfaces. It does not claim any provider or "
            "workflow execution completed successfully."
        ),
        "next_action": (
            "Use the manifest to form controlled, trace-bound P3 and P4 dispatches; preserve "
            "run-level completion results separately."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# BEM-949 P1 — Active workflow dispatch manifest",
        "",
        "| Workflow | Provider | Dispatch | Required inputs | Runtime evidence |",
        "|---|---|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['path']}` | {row['provider']} | "
            f"{'yes' if row['workflow_dispatch_available'] else 'no'} | "
            f"{row['required_input_count']} | {row['manual_dispatch_evidence']} |"
        )
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
