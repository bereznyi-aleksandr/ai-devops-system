#!/usr/bin/env python3
"""BEM-933 Telegram delivery/outbox static audit."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEBHOOK = ROOT / "infrastructure/cloudflare-worker/telegram-webhook.js"
ROUTER = ROOT / ".github/workflows/provider-router.yml"
ENV_DOC = ROOT / "infrastructure/cloudflare-worker/REQUIRED_ENV.md"
WRANGLER = ROOT / "infrastructure/cloudflare-worker/wrangler.toml"
RECEIPT = ROOT / "governance/proofs/BEM933_telegram_delivery_audit_receipt.json"


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def main() -> int:
    webhook = WEBHOOK.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")
    env_doc = ENV_DOC.read_text(encoding="utf-8")
    wrangler = WRANGLER.read_text(encoding="utf-8")

    checks = {
        "deterministic_trace_from_update": (
            'return `tg_${safeUpdateKey}`;' in webhook
            and "traceSuffix" not in webhook
            and "Date.now()" not in webhook
            and "update.update_id ??" in webhook
        ),
        "outbox_trace_duplicate_scan": (
            'json.loads(line).get("trace_id") == trace' in router
            and "if not seen:" in router
            and 'outbox.open("a", encoding="utf-8")' in router
        ),
        "runtime_secrets_boundary_documented": (
            "## Live runtime secret boundary" in env_doc
            and "## Manual and audit boundary" in env_doc
            and "`TELEGRAM_BOT_TOKEN`" in env_doc
            and "`GH_PAT`" in env_doc
            and "Never commit secret values" in env_doc
        ),
        "wrangler_contains_no_secret_assignment": (
            "TELEGRAM_BOT_TOKEN =" not in wrangler
            and "GH_PAT =" not in wrangler
            and "AI_SYSTEM_GITHUB_PAT =" not in wrangler
        ),
    }

    missing = [name for name, passed in checks.items() if not passed]
    receipt = {
        "status": "PASS" if not missing else "BLOCKED",
        "protocol": "BEM-933",
        "task_id": "BEM933-TELEGRAM-DELIVERY-AUDIT",
        "receipt_type": "telegram_delivery_outbox_idempotency_audit",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_sha": git_sha(),
        "checks": checks,
        "missing": missing,
        "boundaries": {
            "live_runtime": [
                "TELEGRAM_BOT_TOKEN",
                "GH_PAT",
                "AI_SYSTEM_GITHUB_PAT",
            ],
            "repo_manual_audit": "secret-free static verification only",
        },
        "idempotency_key": "Telegram update_id -> deterministic trace_id",
        "outbox_rule": "append only when trace_id is not already present",
    }

    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(receipt["status"])
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
