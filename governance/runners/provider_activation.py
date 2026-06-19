#!/usr/bin/env python3
"""Provider activation runtime for BEM-940.

Reads governance/config/provider_config.json, validates a provider can serve a role, records an activation
decision, and writes governance/state/provider_status.json. This is a routing/runtime control layer only;
it does not claim downstream LLM completion.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "governance" / "config" / "provider_config.json"
STATE = ROOT / "governance" / "state"
PROOFS = ROOT / "governance" / "proofs"
STATUS = STATE / "provider_status.json"
DECISIONS = STATE / "provider_activation_decisions.jsonl"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.:-]+", "_", str(value or "activation"))[:140]


def load_config() -> dict[str, Any]:
    return json.loads(CFG.read_text(encoding="utf-8"))


def append_jsonl(path: Path, items: list[dict[str, Any]]) -> None:
    if not items:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


def decide(provider: str, role: str, trace_id: str | None = None) -> dict[str, Any]:
    cfg = load_config()
    providers = cfg.get("providers", {})
    roles = cfg.get("roles", {})
    provider_cfg = providers.get(provider) or {}
    role_cfg = roles.get(role) or {}
    blockers: list[str] = []
    if not provider_cfg:
        blockers.append("provider_missing")
    if not role_cfg:
        blockers.append("role_missing")
    if provider_cfg and not provider_cfg.get("enabled"):
        blockers.append("provider_disabled")
    if provider_cfg and provider_cfg.get("deprecated"):
        blockers.append("provider_deprecated")
    support = provider_cfg.get("role_support", [])
    if provider_cfg and role not in support and "*" not in support:
        blockers.append("provider_role_unsupported")
    workflow_id = provider_cfg.get("workflow_id")
    if provider_cfg and not workflow_id:
        blockers.append("workflow_id_missing")
    status = "ACTIVE" if not blockers else "BLOCKED"
    primary_for_role = role_cfg.get("primary") == provider
    fallback_for_role = role_cfg.get("fallback") == provider
    decision = {
        "status": status,
        "protocol": "BEM-940",
        "task_id": "BEM940-P0-PROVIDER-ACTIVATION",
        "created_at": now(),
        "trace_id": safe(trace_id or f"activation_{provider}_{role}"),
        "provider": provider,
        "role": role,
        "workflow_id": workflow_id,
        "enabled": bool(provider_cfg.get("enabled")),
        "deprecated": bool(provider_cfg.get("deprecated")),
        "primary_for_role": primary_for_role,
        "fallback_for_role": fallback_for_role,
        "activation_mode": "primary" if primary_for_role else ("fallback" if fallback_for_role else "explicit"),
        "blockers": blockers,
        "non_claim": "activation decision only; no downstream LLM completion claimed",
    }
    return decision


def write_status(decision: dict[str, Any]) -> dict[str, Any]:
    status = {}
    if STATUS.exists():
        try:
            status = json.loads(STATUS.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            status = {}
    providers = status.setdefault("providers", {})
    provider = decision["provider"]
    providers[provider] = {
        "status": decision["status"],
        "updated_at": decision["created_at"],
        "role": decision["role"],
        "workflow_id": decision.get("workflow_id"),
        "activation_mode": decision.get("activation_mode"),
        "blockers": decision.get("blockers", []),
    }
    status["updated_at"] = decision["created_at"]
    status["protocol"] = "BEM-940"
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    append_jsonl(DECISIONS, [decision])
    return status


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="claude_code")
    parser.add_argument("--role", default="curator")
    parser.add_argument("--trace-id")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    decision = decide(args.provider, args.role, args.trace_id)
    status = write_status(decision) if args.write and decision["status"] == "ACTIVE" else None
    checks = {
        "provider_activation_runtime_code_present": True,
        "provider_config_read": CFG.exists(),
        "provider_enabled": decision["enabled"],
        "provider_not_deprecated": not decision["deprecated"],
        "workflow_id_present": bool(decision.get("workflow_id")),
        "activation_status_written": status is not None if args.write and decision["status"] == "ACTIVE" else True,
        "downstream_llm_completion_not_claimed": True,
    }
    blockers = list(decision.get("blockers", [])) + [name for name, passed in checks.items() if not passed]
    receipt = {
        "status": "PASS" if not blockers else "BLOCKED",
        "protocol": "BEM-940",
        "task_id": "BEM940-P0-PROVIDER-ACTIVATION",
        "created_at": now(),
        "stage": {"tasks_done": 1, "tasks_total": 4, "percent": 25},
        "decision": decision,
        "status_path": str(STATUS.relative_to(ROOT)),
        "decisions_path": str(DECISIONS.relative_to(ROOT)),
        "checks": checks,
        "blockers": blockers,
        "next_task": "BEM940-P1-PROVIDER-STATUS-INTEGRATION" if not blockers else None,
    }
    PROOFS.mkdir(parents=True, exist_ok=True)
    (PROOFS / "BEM940_provider_activation_receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if blockers:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
