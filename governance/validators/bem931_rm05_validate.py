#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))

def main():
    elements = load("governance/registry/elements_registry.json")["elements"]
    profiles = load("governance/registry/element_prompt_profiles.json")["profiles"]
    rules = load("governance/registry/rule_registry.json")["rules"]

    element_ids = {e["element_id"] for e in elements}
    profile_element_ids = {p["element_id"] for p in profiles}
    if element_ids != profile_element_ids:
        missing_profiles = sorted(element_ids - profile_element_ids)
        extra_profiles = sorted(profile_element_ids - element_ids)
        raise SystemExit(f"FAIL: profile mismatch missing={missing_profiles} extra={extra_profiles}")

    profile_ids = {p["prompt_profile_id"] for p in profiles}
    for e in elements:
        if e["prompt_profile_id"] not in profile_ids:
            raise SystemExit("FAIL: element missing prompt profile: " + e["element_id"])

    rule_versions = {(r["rule_id"], r["rule_version"]) for r in rules}
    for p in profiles:
        if not (ROOT / p["static_role_prompt_ref"]).exists():
            raise SystemExit("FAIL: missing static role prompt: " + p["static_role_prompt_ref"])
        for ref in p.get("dynamic_rule_refs", []):
            if not ref.get("rule_id") or not ref.get("rule_version"):
                raise SystemExit("FAIL: dynamic rule ref missing rule_version")
            if (ref["rule_id"], ref["rule_version"]) not in rule_versions:
                raise SystemExit("FAIL: dynamic rule ref not found in rule_registry: " + str(ref))

    print("PASS: BEM-931 RM05 role prompts and element prompt profiles")

if __name__ == "__main__":
    main()
