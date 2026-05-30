#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OBJECTS = ROOT / "governance/state/objects_registry.json"
MESSAGES = ROOT / "governance/messages/managed_channel_messages.jsonl"
PROMPT_MAP = {"OBJ-GD-001": "governance/prompts/general_director_prompt.md", "OBJ-DIR-001": "governance/prompts/director_prompt.md", "OBJ-WRK-001": "governance/prompts/worker_prompt.md"}

def run_object(object_id, action="status"):
    registry = json.loads(OBJECTS.read_text(encoding="utf-8"))
    objects = {obj["id"]: obj for obj in registry.get("objects", [])}
    if object_id not in objects:
        raise SystemExit("unknown object " + object_id)
    prompt_path = ROOT / PROMPT_MAP[object_id]
    if not prompt_path.exists():
        raise SystemExit("prompt missing for " + object_id)
    result = {"object_id": object_id, "action": action, "status": "completed", "prompt": str(prompt_path.relative_to(ROOT)), "elements": objects[object_id].get("elements", []), "result": "object runner executed deterministic status action"}
    out = ROOT / "governance/objects" / (object_id + "_last_run.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    msg = {"message_id": "MSG-RUN-" + object_id, "task_id": "BEM-910-OBJECT-RUNNER", "trace_id": "bem910_object_runners", "source_object": object_id, "source_curator": "EL-CUR-" + object_id.split("-")[1], "target_object": "OBJ-DIR-001" if object_id != "OBJ-DIR-001" else "OBJ-GD-001", "target_curator": "EL-CUR-DIR-001" if object_id != "OBJ-DIR-001" else "EL-CUR-GD-001", "message_type": "result", "payload_ref": str(out.relative_to(ROOT)), "created_at_utc3": "2026-05-30T08:40:00+03:00", "rule_refs": ["RULE-006", "RULE-011"], "status": "recorded"}
    existing = MESSAGES.read_text(encoding="utf-8") if MESSAGES.exists() else ""
    MESSAGES.write_text(existing + json.dumps(msg, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result

if __name__ == "__main__":
    import sys
    oid = sys.argv[1] if len(sys.argv) > 1 else "OBJ-WRK-001"
    run_object(oid)
