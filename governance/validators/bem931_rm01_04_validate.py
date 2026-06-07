#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))

def main():
    objects = load("governance/registry/objects_registry.json")
    elements = load("governance/registry/elements_registry.json")
    rules = load("governance/registry/rule_registry.json")
    assert {"GD","DIR","WRK"}.issubset({o["object_id"] for o in objects["objects"]})
    object_ids = {o["object_id"] for o in objects["objects"]}
    for e in elements["elements"]:
        assert e["object_id"] in object_ids
        assert e["element_id"] and e["role"] and e["prompt_profile_id"]
    for r in rules["rules"]:
        for field in ["rule_id","rule_version","scope","owner","effective_from","status"]:
            assert r.get(field), f"rule missing {field}"
    print("PASS: BEM-931 RM01-04 foundation registries")

if __name__ == "__main__":
    main()
