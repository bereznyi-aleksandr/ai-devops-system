#!/usr/bin/env python3
"""Install deterministic BEM-934 Claude result materialization into claude.yml."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REQUEST = ROOT / "governance/runtime/bem934_state_request.json"
WORKFLOW = ROOT / ".github/workflows/claude.yml"
RECEIPT = ROOT / "governance/proofs/BEM934_claude_result_materializer_install_receipt.json"
MARKER = "      - name: Write final result to transport\n"
STEP_NAME = "      - name: Materialize BEM-934 binding plan from Claude result\n"
STEP = '      - name: Materialize BEM-934 binding plan from Claude result\n        if: ${{ inputs.task_type == \'object_runtime_binding\' && steps.claude_role.outcome == \'success\' }}\n        shell: bash\n        env:\n          EXECUTION_FILE: ${{ steps.claude_role.outputs.execution_file }}\n          TRACE_ID: ${{ inputs.trace_id }}\n        run: |\n          set -euo pipefail\n          mkdir -p governance/proofs\n          python3 - <<\'PY\'\n          import json\n          import os\n          import re\n          from datetime import datetime, timezone\n          from pathlib import Path\n\n          execution_path = Path(os.environ.get("EXECUTION_FILE", ""))\n          trace_id = os.environ.get("TRACE_ID", "").strip()\n          receipt_path = Path("governance/proofs/BEM934_claude_result_materialization_receipt.json")\n          plan_path = Path("governance/proofs/BEM934_object_binding_plan.json")\n\n          def now():\n              return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")\n\n          def write_receipt(payload):\n              receipt_path.write_text(\n                  json.dumps(payload, ensure_ascii=False, indent=2) + "\\n",\n                  encoding="utf-8",\n              )\n\n          receipt = {\n              "status": "BLOCKED",\n              "protocol": "BEM-934",\n              "task_id": "BEM934-OBJECTS-BOUND",\n              "created_at": now(),\n              "trace_id": trace_id,\n              "execution_file_available": execution_path.exists(),\n              "checks": {},\n              "missing": [],\n          }\n\n          if not trace_id:\n              receipt["blocker"] = "trace_id_missing"\n              write_receipt(receipt)\n              raise SystemExit(0)\n          if not execution_path.exists():\n              receipt["blocker"] = "execution_file_missing"\n              write_receipt(receipt)\n              raise SystemExit(0)\n\n          result_text = None\n          for raw_line in execution_path.read_text(encoding="utf-8", errors="replace").splitlines():\n              raw_line = raw_line.strip()\n              if not raw_line:\n                  continue\n              try:\n                  event = json.loads(raw_line)\n              except json.JSONDecodeError:\n                  continue\n              if isinstance(event, dict) and event.get("type") == "result":\n                  value = event.get("result")\n                  if isinstance(value, str) and value.strip():\n                      result_text = value.strip()\n\n          receipt["checks"]["final_result_event_present"] = bool(result_text)\n          if not result_text:\n              receipt["blocker"] = "claude_final_result_missing"\n              receipt["missing"] = ["final_result_event_present"]\n              write_receipt(receipt)\n              raise SystemExit(0)\n\n          candidates = [result_text]\n          fenced = re.findall(r"```(?:json)?\\s*(\\{.*?\\})\\s*```", result_text, flags=re.S | re.I)\n          candidates.extend(fenced)\n          start, end = result_text.find("{"), result_text.rfind("}")\n          if start >= 0 and end > start:\n              candidates.append(result_text[start:end + 1])\n\n          plan = None\n          for candidate in candidates:\n              try:\n                  parsed = json.loads(candidate)\n              except json.JSONDecodeError:\n                  continue\n              if isinstance(parsed, dict):\n                  plan = parsed\n                  break\n\n          receipt["checks"]["strict_json_object_parsed"] = isinstance(plan, dict)\n          if not isinstance(plan, dict):\n              receipt["blocker"] = "claude_result_not_strict_json"\n              receipt["missing"] = ["strict_json_object_parsed"]\n              write_receipt(receipt)\n              raise SystemExit(0)\n\n          required = ("objective", "assumptions", "steps", "acceptance", "risks", "trace_id")\n          steps = plan.get("steps")\n          acceptance = plan.get("acceptance")\n          text = json.dumps(plan, ensure_ascii=False).lower()\n          checks = {\n              "required_fields_present": all(field in plan for field in required),\n              "trace_matches": plan.get("trace_id") == trace_id,\n              "steps_are_task_specific": isinstance(steps, list) and len([x for x in steps if str(x).strip()]) >= 3,\n              "acceptance_is_verifiable": isinstance(acceptance, list) and len([x for x in acceptance if str(x).strip()]) >= 2,\n              "mentions_wrk_c1": "wrk-c1" in text or "wrk_c1" in text,\n              "mentions_claude_provider": "claude" in text,\n              "mentions_object_runtime_binding": all(term in text for term in ("object", "runtime", "binding")),\n              "mentions_idempotent_telegram_routing": all(term in text for term in ("idempotent", "telegram", "routing")),\n          }\n          receipt["checks"].update(checks)\n          receipt["missing"] = [key for key, value in receipt["checks"].items() if not value]\n          if receipt["missing"]:\n              receipt["blocker"] = "claude_plan_semantic_validation_failed"\n              write_receipt(receipt)\n              raise SystemExit(0)\n\n          plan_path.write_text(\n              json.dumps(plan, ensure_ascii=False, indent=2) + "\\n",\n              encoding="utf-8",\n          )\n          receipt.update({\n              "status": "PASS",\n              "plan_path": str(plan_path),\n              "execution_file_committed": False,\n              "raw_execution_log_retained_ephemerally_only": True,\n          })\n          receipt.pop("blocker", None)\n          write_receipt(receipt)\n          PY\n\n          git config user.email "bem934-claude-materializer@ai-devops-system"\n          git config user.name "BEM-934 Claude Materializer"\n          git pull --rebase --autostash origin main || true\n          git add governance/proofs/BEM934_claude_result_materialization_receipt.json\n          if [ -f governance/proofs/BEM934_object_binding_plan.json ]; then\n            git add governance/proofs/BEM934_object_binding_plan.json\n          fi\n          if git diff --cached --quiet; then\n            echo "No materialized Claude proof changes"\n          else\n            git commit -m "Materialize BEM-934 Claude binding proof trace=${{ inputs.trace_id }}"\n            git push || (git pull --rebase origin main && git push)\n          fi\n'


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, cwd=ROOT, text=True, capture_output=True, check=False
    )


def write(payload: dict[str, Any]) -> None:
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    request = json.loads(REQUEST.read_text(encoding="utf-8"))
    action = str(request.get("action") or "").strip()
    receipt: dict[str, Any] = {
        "status": "BLOCKED",
        "protocol": "BEM-934",
        "task_id": "BEM934-CLAUDE-RESULT-MATERIALIZER-INSTALL",
        "created_at": now(),
        "action": action,
        "checks": {},
        "missing": [],
    }
    if action != "install_claude_result_materializer":
        receipt["blocker"] = "unsupported_action"
        write(receipt)
        return 0

    pull = run(["git", "pull", "--rebase", "--autostash", "origin", "main"])
    if pull.returncode != 0:
        receipt["blocker"] = "git_pull_failed"
        receipt["git_pull_stderr"] = pull.stderr[-2000:]
        write(receipt)
        return 0

    source = WORKFLOW.read_text(encoding="utf-8")
    already_present = STEP_NAME in source
    if not already_present:
        if MARKER not in source:
            receipt["blocker"] = "workflow_insertion_marker_missing"
            write(receipt)
            return 0
        source = source.replace(MARKER, STEP + "\n" + MARKER, 1)
        WORKFLOW.write_text(source, encoding="utf-8")

    updated = WORKFLOW.read_text(encoding="utf-8")
    checks = {
        "materializer_step_present": STEP_NAME in updated,
        "execution_file_output_consumed": 'steps.claude_role.outputs.execution_file' in updated,
        "trace_input_consumed": "TRACE_ID: ${{ inputs.trace_id }}" in updated,
        "raw_execution_file_not_git_added": "git add $EXECUTION_FILE" not in updated,
        "sanitized_plan_path_present": "governance/proofs/BEM934_object_binding_plan.json" in updated,
        "materialization_receipt_path_present": "governance/proofs/BEM934_claude_result_materialization_receipt.json" in updated,
        "strict_validation_present": "claude_plan_semantic_validation_failed" in updated,
    }
    receipt["checks"] = checks
    receipt["missing"] = [k for k, v in checks.items() if not v]
    receipt["changed"] = not already_present
    if receipt["missing"]:
        receipt["blocker"] = "materializer_install_validation_failed"
        write(receipt)
        return 0

    run(["git", "config", "user.email", "bem934-materializer@ai-devops-system"])
    run(["git", "config", "user.name", "BEM-934 Materializer"])
    run(["git", "add", ".github/workflows/claude.yml"])
    diff = run(["git", "diff", "--cached", "--quiet"])
    if diff.returncode != 0:
        commit = run(["git", "commit", "-m", "Add BEM-934 Claude result materializer"])
        if commit.returncode != 0:
            receipt["blocker"] = "git_commit_failed"
            receipt["git_commit_stderr"] = commit.stderr[-2000:]
            write(receipt)
            return 0
        push = run(["git", "push"])
        if push.returncode != 0:
            pull2 = run(["git", "pull", "--rebase", "origin", "main"])
            push2 = run(["git", "push"]) if pull2.returncode == 0 else pull2
            if pull2.returncode != 0 or push2.returncode != 0:
                receipt["blocker"] = "git_push_failed"
                receipt["git_push_stderr"] = (pull2.stderr + "\n" + push2.stderr)[-3000:]
                write(receipt)
                return 0

    head = run(["git", "rev-parse", "HEAD"])
    receipt.update({
        "status": "PASS",
        "source_commit_sha": head.stdout.strip() if head.returncode == 0 else None,
        "workflow_path": ".github/workflows/claude.yml",
        "raw_execution_log_committed": False,
    })
    receipt.pop("blocker", None)
    write(receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
