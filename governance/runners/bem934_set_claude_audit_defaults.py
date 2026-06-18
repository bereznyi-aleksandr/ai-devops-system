#!/usr/bin/env python3
from pathlib import Path

PATH = Path(".github/workflows/claude.yml")
TRACE = "bem934_close_external_audit_20260618"
TASK = (
    "BEM-934 independent external closure audit. Act only as EXTERNAL_AUDITOR_CLAUDE. "
    "Read governance/protocols/BEM934_Protocol.md, governance/roadmap/ACTIVE_QUEUE.json, "
    "governance/proofs/BEM934_live_test_receipt.json, governance/proofs/BEM934_objects_bound_receipt.json, "
    "governance/proofs/BEM934_close_preparation_receipt.json, governance/config/provider_config.json, "
    "governance/AGENT_CONTEXT.md, and SYSTEM_STATUS.md. Directly verify cited repository files and SHA evidence. "
    "Create exactly governance/proofs/BEM934_external_auditor_verdict.json. "
    "The JSON must contain status PASS or BLOCKED, protocol BEM-934, task_id BEM934-CLOSE, "
    "auditor EXTERNAL_AUDITOR_CLAUDE, trace_id bem934_close_external_audit_20260618, "
    "created_at, checks with explicit booleans, evidence_paths, blockers as a list, and verdict. "
    "PASS is allowed only when the real Telegram ingress is non-replay, provider_selected is claude_code, "
    "target workflow is claude.yml, exact live transport is completed with no blocker, all prior receipts are PASS, "
    "self-hosted is deprecated, and gpt_codex_cloud is described only as mechanical_fallback without LLM capability. "
    "Do not modify ACTIVE_QUEUE, AGENT_CONTEXT, SYSTEM_STATUS, provider_config, or any existing receipt."
)
DEFAULTS = {
    "role": "auditor",
    "provider": "claude_code",
    "trace_id": TRACE,
    "cycle_id": "bem934_close_external_audit",
    "task_type": "external_audit",
    "task": TASK,
}

def quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"

def main() -> None:
    lines = PATH.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index("    inputs:")
    except ValueError as exc:
        raise SystemExit("workflow_dispatch inputs block not found") from exc
    end = next(
        i for i in range(start + 1, len(lines))
        if lines[i] and not lines[i].startswith(" ")
    )
    found = set()
    i = start + 1
    while i < end:
        line = lines[i]
        if line.startswith("      ") and not line.startswith("        ") and line.endswith(":"):
            key = line.strip()[:-1]
            block_start = i
            j = i + 1
            while j < end and not (
                lines[j].startswith("      ")
                and not lines[j].startswith("        ")
                and lines[j].endswith(":")
            ):
                j += 1
            if key in DEFAULTS:
                found.add(key)
                block = lines[block_start:j]
                required_seen = False
                default_seen = False
                type_index = None
                for k, item in enumerate(block):
                    stripped = item.strip()
                    if stripped.startswith("required:"):
                        block[k] = "        required: false"
                        required_seen = True
                    elif stripped.startswith("default:"):
                        block[k] = "        default: " + quote(DEFAULTS[key])
                        default_seen = True
                    elif stripped.startswith("type:"):
                        type_index = k
                insert_at = type_index if type_index is not None else len(block)
                if not required_seen:
                    block.insert(insert_at, "        required: false"
                    insert_at += 1
                if not default_seen:
                    block.insert(insert_at, "        default: " + quote(DEFAULTS[key]))
                lines[block_start:j] = block
                delta = len(block) - (j - block_start)
                end += delta
                i = j + delta
                continue
        i += 1
    missing = sorted(set(DEFAULTS) - found)
    if missing:
        raise SystemExit(f"input blocks not found: {missing}")
    PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
