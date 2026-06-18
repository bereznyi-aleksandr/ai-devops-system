#!/usr/bin/env python3
from pathlib import Path

PATH = Path(".github/workflows/claude.yml")
KEYS = {"role", "provider", "trace_id", "cycle_id", "task_type", "task"}

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
            if key in KEYS:
                found.add(key)
                block = [item for item in lines[block_start:j] if not item.strip().startswith("default:")]
                required_seen = False
                type_index = None
                for k, item in enumerate(block):
                    stripped = item.strip()
                    if stripped.startswith("required:"):
                        block[k] = "        required: true"
                        required_seen = True
                    elif stripped.startswith("type:"):
                        type_index = k
                if not required_seen:
                    insert_at = type_index if type_index is not None else len(block)
                    block.insert(insert_at, "        required: true")
                lines[block_start:j] = block
                delta = len(block) - (j - block_start)
                end += delta
                i = j + delta
                continue
        i += 1
    missing = sorted(KEYS - found)
    if missing:
        raise SystemExit(f"input blocks not found: {missing}")
    PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
