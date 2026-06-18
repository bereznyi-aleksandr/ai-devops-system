#!/usr/bin/env python3
# Install a dedicated Claude structured-output path for BEM-934 object binding.
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REQUEST = ROOT / "governance/runtime/bem934_state_request.json"
WORKFLOW = ROOT / ".github/workflows/claude.yml"
RECEIPT = ROOT / "governance/proofs/BEM934_binding_structured_output_install_receipt.json"

PRIMARY_HEADER = '''      - name: Run Claude Code role
        id: claude_role
        if: github.event_name == 'workflow_dispatch'
'''
PRIMARY_HEADER_FIXED = '''      - name: Run Claude Code role
        id: claude_role
        if: github.event_name == 'workflow_dispatch' && inputs.task_type != 'object_runtime_binding'
'''
LEGACY_MARKER = "      - name: Run Claude Code legacy\n"
MATERIALIZER_START = "      - name: Materialize BEM-934 binding plan from Claude result\n"
MATERIALIZER_STRUCTURED_START = "      - name: Materialize BEM-934 binding plan from Claude structured output\n"
TRANSPORT_MARKER = "      - name: Write final result to transport\n"

SCHEMA = (
    '{"type":"object","properties":{'
    '"objective":{"type":"string"},'
    '"assumptions":{"type":"array","items":{"type":"string"}},'
    '"steps":{"type":"array","items":{"type":"string"},"minItems":3},'
    '"acceptance":{"type":"array","items":{"type":"string"},"minItems":2},'
    '"risks":{"type":"array","items":{"type":"string"}},'
    '"trace_id":{"type":"string"}'
    '},"required":["objective","assumptions","steps","acceptance","risks","trace_id"],'
    '"additionalProperties":false}'
)

BINDING_STEP = f'''      - name: Run Claude Code binding role with structured output
        id: claude_binding_role
        if: github.event_name == 'workflow_dispatch' && inputs.task_type == 'object_runtime_binding'
        continue-on-error: true
        uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: ${{{{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}}}
          github_token: ${{{{ secrets.AI_SYSTEM_GITHUB_PAT }}}}
          prompt_file: ${{{{ env.PROMPT_FILE }}}}
          claude_args: >-
            --max-turns 10
            --allowedTools "Read,Glob,Grep"
            --json-schema '{SCHEMA}'

'''

MATERIALIZER_STEP = r'''      - name: Materialize BEM-934 binding plan from Claude structured output
        if: ${{ inputs.task_type == 'object_runtime_binding' && steps.claude_binding_role.outcome == 'success' }}
        shell: bash
        env:
          STRUCTURED_OUTPUT: ${{ steps.claude_binding_role.outputs.structured_output }}
          TRACE_ID: ${{ inputs.trace_id }}
        run: |
          set -euo pipefail
          mkdir -p governance/proofs
          python3 - <<'PY'
          import json
          import os
          from datetime import datetime, timezone
          from pathlib import Path

          trace_id = os.environ.get("TRACE_ID", "").strip()
          structured_raw = os.environ.get("STRUCTURED_OUTPUT", "").strip()
          receipt_path = Path("governance/proofs/BEM934_claude_result_materialization_receipt.json")
          plan_path = Path("governance/proofs/BEM934_object_binding_plan.json")

          def now():
              return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

          def write_receipt(payload):
              receipt_path.write_text(
                  json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                  encoding="utf-8",
              )

          receipt = {
              "status": "BLOCKED",
              "protocol": "BEM-934",
              "task_id": "BEM934-OBJECTS-BOUND",
              "created_at": now(),
              "trace_id": trace_id,
              "structured_output_available": bool(structured_raw),
              "checks": {},
              "missing": [],
          }

          if not trace_id:
              receipt["blocker"] = "trace_id_missing"
              write_receipt(receipt)
              raise SystemExit(0)
          if not structured_raw:
              receipt["blocker"] = "structured_output_missing"
              receipt["missing"] = ["structured_output_available"]
              write_receipt(receipt)
              raise SystemExit(0)

          try:
              plan = json.loads(structured_raw)
          except json.JSONDecodeError as error:
              receipt["blocker"] = "structured_output_not_strict_json"
              receipt["json_error"] = str(error)
              receipt["missing"] = ["strict_json_object_parsed"]
              write_receipt(receipt)
              raise SystemExit(0)

          required = ("objective", "assumptions", "steps", "acceptance", "risks", "trace_id")
          steps = plan.get("steps")
          acceptance = plan.get("acceptance")
          text = json.dumps(plan, ensure_ascii=False).lower()
          checks = {
              "strict_json_object_parsed": isinstance(plan, dict),
              "required_fields_present": all(field in plan for field in required),
              "trace_matches": plan.get("trace_id") == trace_id,
              "steps_are_task_specific": isinstance(steps, list)
                  and len([item for item in steps if str(item).strip()]) >= 3,
              "acceptance_is_verifiable": isinstance(acceptance, list)
                  and len([item for item in acceptance if str(item).strip()]) >= 2,
              "mentions_wrk_c1": "wrk-c1" in text or "wrk_c1" in text,
              "mentions_claude_provider": "claude" in text,
              "mentions_object_runtime_binding": all(
                  term in text for term in ("object", "runtime", "binding")
              ),
              "mentions_idempotent_telegram_routing": all(
                  term in text for term in ("idempotent", "telegram", "routing")
              ),
          }
          receipt["checks"] = checks
          receipt["missing"] = [key for key, value in checks.items() if not value]
          if receipt["missing"]:
              receipt["blocker"] = "claude_structured_plan_semantic_validation_failed"
              write_receipt(receipt)
              raise SystemExit(0)

          plan_path.write_text(
              json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
              encoding="utf-8",
          )
          receipt.update({
              "status": "PASS",
              "plan_path": str(plan_path),
              "raw_execution_log_committed": False,
              "source": "claude_code_action_structured_output",
          })
          receipt.pop("blocker", None)
          write_receipt(receipt)
          PY

          git config user.email "bem934-claude-materializer@ai-devops-system"
          git config user.name "BEM-934 Claude Materializer"
          git pull --rebase --autostash origin main || true
          git add governance/proofs/BEM934_claude_result_materialization_receipt.json
          if [ -f governance/proofs/BEM934_object_binding_plan.json ]; then
            git add governance/proofs/BEM934_object_binding_plan.json
          fi
          if git diff --cached --quiet; then
            echo "No structured Claude proof changes"
          else
            git commit -m "Materialize BEM-934 Claude binding proof trace=${{ inputs.trace_id }}"
            git push || (git pull --rebase origin main && git push)
          fi

'''

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)

def write(payload: dict[str, Any]) -> None:
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def main() -> int:
    request = json.loads(REQUEST.read_text(encoding="utf-8"))
    action = str(request.get("action") or "").strip()
    receipt: dict[str, Any] = {
        "status": "BLOCKED",
        "protocol": "BEM-934",
        "task_id": "BEM934-BINDING-STRUCTURED-OUTPUT-INSTALL",
        "created_at": now(),
        "action": action,
        "checks": {},
        "missing": [],
    }
    if action != "install_binding_structured_output":
        receipt["blocker"] = "unsupported_action"
        write(receipt)
        return 0

    pull = run(["git", "pull", "--rebase", "--autostash", "origin", "main"])
    if pull.returncode != 0:
        receipt["blocker"] = "git_pull_failed"
        receipt["stderr"] = pull.stderr[-2000:]
        write(receipt)
        return 0

    source = WORKFLOW.read_text(encoding="utf-8")
    changed = False

    if PRIMARY_HEADER in source:
        source = source.replace(PRIMARY_HEADER, PRIMARY_HEADER_FIXED, 1)
        changed = True
    elif PRIMARY_HEADER_FIXED not in source:
        receipt["blocker"] = "primary_claude_step_marker_missing"
        write(receipt)
        return 0

    if "id: claude_binding_role\n" not in source:
        if LEGACY_MARKER not in source:
            receipt["blocker"] = "legacy_step_marker_missing"
            write(receipt)
            return 0
        source = source.replace(LEGACY_MARKER, BINDING_STEP + LEGACY_MARKER, 1)
        changed = True

    start = source.find(MATERIALIZER_START)
    if start < 0:
        start = source.find(MATERIALIZER_STRUCTURED_START)
    end = source.find(TRANSPORT_MARKER)
    if start < 0 or end < 0 or end <= start:
        receipt["blocker"] = "materializer_or_transport_marker_missing"
        write(receipt)
        return 0
    current_materializer = source[start:end]
    desired_materializer = MATERIALIZER_STEP + "\n"
    if current_materializer != desired_materializer:
        source = source[:start] + desired_materializer + source[end:]
        changed = True

    old_outcome = "          CLAUDE_OUTCOME: ${{ steps.claude_role.outcome }}"
    new_outcome = (
        "          CLAUDE_OUTCOME: ${{ inputs.task_type == 'object_runtime_binding' "
        "&& steps.claude_binding_role.outcome || steps.claude_role.outcome }}"
    )
    if old_outcome in source:
        source = source.replace(old_outcome, new_outcome, 1)
        changed = True
    elif new_outcome not in source:
        receipt["blocker"] = "transport_outcome_marker_missing"
        write(receipt)
        return 0

    WORKFLOW.write_text(source, encoding="utf-8")
    updated = WORKFLOW.read_text(encoding="utf-8")
    checks = {
        "normal_role_excludes_binding": PRIMARY_HEADER_FIXED in updated,
        "dedicated_binding_role_present": "id: claude_binding_role\n" in updated,
        "json_schema_present": "--json-schema" in updated and '"trace_id":{"type":"string"}' in updated,
        "structured_output_consumed": "steps.claude_binding_role.outputs.structured_output" in updated,
        "materializer_fail_closed": "structured_output_missing" in updated,
        "sanitized_plan_path_present": "governance/proofs/BEM934_object_binding_plan.json" in updated,
        "raw_execution_log_not_added": "git add $EXECUTION_FILE" not in updated,
        "transport_uses_binding_outcome": new_outcome in updated,
    }
    receipt["checks"] = checks
    receipt["missing"] = [key for key, value in checks.items() if not value]
    receipt["changed"] = changed
    if receipt["missing"]:
        receipt["blocker"] = "structured_output_install_validation_failed"
        write(receipt)
        return 0

    run(["git", "config", "user.email", "bem934-structured-output@ai-devops-system"])
    run(["git", "config", "user.name", "BEM-934 Structured Output"])
    run(["git", "add", ".github/workflows/claude.yml"])
    diff = run(["git", "diff", "--cached", "--quiet"])
    if diff.returncode != 0:
        commit = run(["git", "commit", "-m", "Add BEM-934 Claude structured binding output"])
        if commit.returncode != 0:
            receipt["blocker"] = "git_commit_failed"
            receipt["stderr"] = commit.stderr[-2000:]
            write(receipt)
            return 0
        push = run(["git", "push"])
        if push.returncode != 0:
            pull2 = run(["git", "pull", "--rebase", "origin", "main"])
            push2 = run(["git", "push"]) if pull2.returncode == 0 else pull2
            if pull2.returncode != 0 or push2.returncode != 0:
                receipt["blocker"] = "git_push_failed"
                receipt["stderr"] = (pull2.stderr + "\n" + push2.stderr)[-3000:]
                write(receipt)
                return 0

    head = run(["git", "rev-parse", "HEAD"])
    receipt.update({
        "status": "PASS",
        "source_commit_sha": head.stdout.strip() if head.returncode == 0 else None,
        "workflow_path": ".github/workflows/claude.yml",
        "structured_output_source": "anthropics/claude-code-action@v1",
        "raw_execution_log_committed": False,
    })
    receipt.pop("blocker", None)
    write(receipt)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
