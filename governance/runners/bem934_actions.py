#!/usr/bin/env python3
"""BEM-934 request-driven repository actions executed by GitHub-hosted runner."""

from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REQUEST = ROOT / "governance/runtime/bem934_state_request.json"
PROOFS = ROOT / "governance/proofs"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_receipt(name: str, payload: dict[str, Any]) -> Path:
    PROOFS.mkdir(parents=True, exist_ok=True)
    path = PROOFS / name
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def deprecate_selfhosted() -> None:
    marker = (
        "# DEPRECATED: requires self-hosted runner, operator will never "
        "provide one. See BEM-934."
    )
    targets = [
        ROOT / ".github/workflows/codex-local.yml",
        ROOT / ".github/workflows/codex-local-assembled.yml",
    ]
    changed: list[str] = []
    checks: dict[str, Any] = {}
    for path in targets:
        text = path.read_text(encoding="utf-8")
        if not text.startswith(marker):
            path.write_text(marker + "\n" + text, encoding="utf-8")
            changed.append(str(path.relative_to(ROOT)))
        updated = path.read_text(encoding="utf-8")
        checks[str(path.relative_to(ROOT))] = {
            "deprecated_marker": updated.startswith(marker),
            "historical_file_retained": path.exists(),
        }
    status = (
        "PASS"
        if all(
            item["deprecated_marker"] and item["historical_file_retained"]
            for item in checks.values()
        )
        else "BLOCKED"
    )
    write_receipt(
        "BEM934_deprecate_selfhosted_receipt.json",
        {
            "status": status,
            "protocol": "BEM-934",
            "task_id": "BEM934-DEPRECATE-SELFHOSTED",
            "created_at": utc_now(),
            "checks": checks,
            "changed_files": changed,
            "active_target_policy": "FORBID_NEW_REFERENCES_TO_CODEX_LOCAL",
        },
    )
    if status != "PASS":
        raise SystemExit(1)


def reconnect_prompt_assembler() -> None:
    workflow_path = ROOT / ".github/workflows/claude.yml"
    text = workflow_path.read_text(encoding="utf-8")
    bridge_marker = "      # BEM-934 prompt assembler bridge"
    build_anchor = "      - name: Build Claude role prompt\n"
    assembler_step = """      # BEM-934 prompt assembler bridge
      - name: Assemble governed role prompt
        if: github.event_name == 'workflow_dispatch'
        shell: bash
        env:
          INPUT_ROLE: ${{ inputs.role }}
        run: |
          set -euo pipefail
          case "$INPUT_ROLE" in
            curator) ELEMENT_ID="WRK.CURATOR" ;;
            analyst) ELEMENT_ID="WRK.ANALYST" ;;
            auditor) ELEMENT_ID="WRK.AUDITOR" ;;
            executor) ELEMENT_ID="WRK.EXECUTOR" ;;
            *) echo "Unsupported role: $INPUT_ROLE"; exit 2 ;;
          esac
          OUT="$RUNNER_TEMP/assembled_role_prompt.md"
          python3 -m py_compile scripts/prompt_assembler.py
          python3 scripts/prompt_assembler.py --element-id "$ELEMENT_ID" --out "$OUT"
          test -s "$OUT"
          echo "ASSEMBLED_ROLE_PROMPT=$OUT" >> "$GITHUB_ENV"

"""
    changed = False
    if bridge_marker not in text:
        if build_anchor not in text:
            raise SystemExit("Build Claude role prompt anchor not found")
        text = text.replace(build_anchor, assembler_step + build_anchor, 1)
        changed = True

    task_anchor = "          task      = os.environ.get('INPUT_TASK', '')\n"
    assembled_block = (
        "          # BEM-934 governed prompt bridge\n"
        "          assembled_path = os.environ.get('ASSEMBLED_ROLE_PROMPT', '')\n"
        "          assembled_text = (\n"
        "              Path(assembled_path).read_text(encoding='utf-8').strip()\n"
        "              if assembled_path and Path(assembled_path).exists()\n"
        "              else ''\n"
        "          )\n"
    )
    if "# BEM-934 governed prompt bridge" not in text:
        if task_anchor not in text:
            raise SystemExit("Claude task anchor not found")
        text = text.replace(task_anchor, task_anchor + assembled_block, 1)
        changed = True

    parts_anchor = "          parts = [\n"
    parts_block = (
        "          parts = [\n"
        "              '# BEM-934 GOVERNED ASSEMBLED ROLE PROMPT',\n"
        "              '',\n"
        "              assembled_text,\n"
        "              '',\n"
    )
    if "# BEM-934 GOVERNED ASSEMBLED ROLE PROMPT" not in text:
        if parts_anchor not in text:
            raise SystemExit("Claude prompt parts anchor not found")
        text = text.replace(parts_anchor, parts_block, 1)
        changed = True

    workflow_path.write_text(text, encoding="utf-8")

    with tempfile.TemporaryDirectory() as temp_dir:
        prompt_path = Path(temp_dir) / "analyst_prompt.md"
        subprocess.run(
            [
                "python3",
                str(ROOT / "scripts/prompt_assembler.py"),
                "--element-id",
                "WRK.ANALYST",
                "--out",
                str(prompt_path),
            ],
            cwd=ROOT,
            check=True,
        )
        prompt = prompt_path.read_text(encoding="utf-8")

    updated = workflow_path.read_text(encoding="utf-8")
    checks = {
        "bridge_step_present": bridge_marker in updated,
        "assembler_cli_present": "scripts/prompt_assembler.py --element-id" in updated,
        "assembled_prompt_injected": "# BEM-934 GOVERNED ASSEMBLED ROLE PROMPT" in updated,
        "static_role_prompt_present": "STATIC ROLE PROMPT" in prompt,
        "council_rule_present": "COUNCIL_ANALYST" in prompt,
        "assembled_prompt_nonempty": len(prompt.encode("utf-8")) > 300,
    }
    status = "PASS" if all(checks.values()) else "BLOCKED"
    write_receipt(
        "BEM934_prompt_assembler_reconnect_receipt.json",
        {
            "status": status,
            "protocol": "BEM-934",
            "task_id": "BEM934-PROMPT-ASSEMBLER-RECONNECT",
            "created_at": utc_now(),
            "workflow": ".github/workflows/claude.yml",
            "changed": changed,
            "checks": checks,
            "assembled_prompt_bytes": len(prompt.encode("utf-8")),
            "missing": [key for key, value in checks.items() if not value],
        },
    )
    if status != "PASS":
        raise SystemExit(1)


ACTIONS = {
    "deprecate_selfhosted": deprecate_selfhosted,
    "reconnect_prompt_assembler": reconnect_prompt_assembler,
}


def main() -> int:
    request = json.loads(REQUEST.read_text(encoding="utf-8"))
    action = str(request.get("action") or "").strip()
    if not action:
        return 0
    handler = ACTIONS.get(action)
    if handler is None:
        raise SystemExit(f"unsupported BEM-934 action: {action}")
    handler()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
