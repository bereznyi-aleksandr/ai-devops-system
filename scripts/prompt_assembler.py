#!/usr/bin/env python3
"""BEM-932 prompt assembler.

For an element_id, read element_prompt_profiles.json, load static role prompt, resolve
dynamic_rule_refs through rule_registry.json, and concatenate the final prompt for codex exec.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]
PROFILES_PATH = ROOT / "governance" / "registry" / "element_prompt_profiles.json"
RULES_PATH = ROOT / "governance" / "registry" / "rule_registry.json"


class PromptAssemblyError(RuntimeError):
    """Raised when a prompt cannot be assembled deterministically."""


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text_or_placeholder(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return f"[STATIC ROLE PROMPT MISSING: {path.as_posix()}]"


def _profiles_by_element(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    profiles = data.get("profiles", [])
    if not isinstance(profiles, list):
        raise PromptAssemblyError("element_prompt_profiles.json: profiles must be list")
    return {str(p.get("element_id")): p for p in profiles if isinstance(p, dict)}


def _rules_by_id(data: Dict[str, Any]) -> Dict[tuple[str, str], Dict[str, Any]]:
    rules = data.get("rules", [])
    if not isinstance(rules, list):
        raise PromptAssemblyError("rule_registry.json: rules must be list")
    result: Dict[tuple[str, str], Dict[str, Any]] = {}
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        key = (str(rule.get("rule_id")), str(rule.get("rule_version")))
        result[key] = rule
    return result


def assemble_prompt(element_id: str, profiles_path: Path = PROFILES_PATH, rules_path: Path = RULES_PATH) -> str:
    """Return assembled prompt text for element_id."""
    profiles = _profiles_by_element(_read_json(profiles_path))
    rules = _rules_by_id(_read_json(rules_path))

    profile = profiles.get(element_id)
    if not profile:
        raise PromptAssemblyError(f"profile not found for element_id={element_id}")

    static_ref = profile.get("static_role_prompt_ref")
    if not static_ref:
        raise PromptAssemblyError(f"static_role_prompt_ref missing for {element_id}")

    sections: List[str] = [
        f"# ASSEMBLED PROMPT | {element_id}",
        "",
        "## STATIC ROLE PROMPT",
        _read_text_or_placeholder(ROOT / str(static_ref)),
        "",
        "2# DYNAMIC SYSTEM RULES",
    ]

    refs = profile.get("dynamic_rule_refs", [])
    if not isinstance(refs, list):
        raise PromptAssemblyError(f"dynamic_rule_refs must be list for {element_id}")

    for ref in refs:
        if not isinstance(ref, dict):
            continue
        rule_id = str(ref.get("rule_id"))
        rule_version = str(ref.get("rule_version", "1.0.0"))
        rule = rules.get((rule_id, rule_version))
        if not rule:
            raise PromptAssemblyError(f"rule not found: {rule_id}@{rule_version}")
        sections.extend([
            "",
            f"### {rule_id}@{rule_version}",
            str(rule.get("body", "")).strip(),
        ])

    return "\n".join(sections).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Assemble BEM prompt for an element")
    parser.add_argument("--element-id", required=True)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    prompt = assemble_prompt(args.element_id)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(prompt, encoding="utf-8")
    else:
        print(prompt, end="")


if __name__ == "__main__":
    main()
