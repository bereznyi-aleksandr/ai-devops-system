#!/usr/bin/env python3
from pathlib import Path

PATH = Path(".github/workflows/claude.yml")
TRACE = "tg_818730867_20260618T105741Z"
TASK = (
    "BEM-934 real operator Telegram live trace tg_818730867_20260618T105741Z. "
    "Verify governance/proofs/BEM932_provider_router_tg_818730867_20260618T105741Z.json. "
    "Create governance/proofs/BEM934_live_content_tg_818730867_20260618T105741Z.json "
    "with status PASS, protocol BEM-934, task_id BEM934-LIVE-TEST, exact trace_id, "
    "provider_selected claude_code, exact source_router_receipt, exactly two verifiable "
    "idempotency invariants for Telegram delivery into WRK-C1, at least two validation_steps, "
    "at least two acceptance_checks each result PASS, and at least one limitation. "
    "Produce a substantive report. Do not modify canonical closure state."
)

DEFAULTS = {
    "role": "curator",
    "provider": "claude_code",
    "trace_id": TRACE,
    "cycle_id": "bem934_live_operator_actual_final",
    "task_type": "live_content_analysis_repair",
    "task": TASK,
}

def quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"

def main() -> None:
    lines = PATH.read_text(encoding="utf-8").splitlines()
    start = lines.index("    inputs:")
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("  issue_comment:"))
    i = start + 1
    found = set()
    while i < end:
        line = lines[i]
        if line.startswith("      ") and line.endswith(":") and not line.startswith("        "):
            key = line.strip()[:-1]
            block_start = i
            j = i + 1
            while j < end and not (
                lines[j].startswith("      ")
                and lines[j].endswith(":")
                and not lines[j].startswith("        ")
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
                if not required_seen:
                    insert_at = type_index if type_index is not None else len(block)
                    block.insert(insert_at, "        required: false")
                    if type_index is not None:
                        type_index += 1
                if not default_seen:
                    insert_at = type_index if type_index is not None else len(block)
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
