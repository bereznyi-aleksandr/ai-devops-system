#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "governance" / "architecture"
PASS = BASE / "object_passports"

def load(rel: Path):
    text = rel.read_text(encoding="utf-8")
    assert len(text.encode("utf-8")) > 200, f"{rel} is too small"
    return json.loads(text)

def main() -> int:
    gd = load(PASS / "GD.json")
    director = load(PASS / "DIR.json")
    wrk = load(PASS / "WRK.json")
    registry = load(BASE / "objects_registry_v2.json")

    assert gd["object_id"] == "GD"
    assert director["object_id"] == "DIR"
    assert wrk["object_id"] == "WRK"

    assert [c["contour_id"] for c in gd["contours"]] == ["GD-C1", "GD-C2"]
    assert [c["contour_id"] for c in director["contours"]] == ["DIR-C1", "DIR-C2"]
    assert [c["contour_id"] for c in wrk["contours"]] == ["WRK-C1", "WRK-C2", "WRK-C3"]

    bad = {"ANALYSIS_CONTOUR", "AUDIT_CONTOUR", "EXECUTION_CONTOUR"}
    wrk_text = (PASS / "WRK.json").read_text(encoding="utf-8")
    for token in bad:
        assert token not in wrk_text, f"legacy erroneous contour token found: {token}"

    for passport in [gd, director, wrk]:
        assert passport["runtime_provider"] == "codex_local"
        assert passport["curator_runner"].startswith("governance/runners/")
        for contour in passport["contours"]:
            assert contour["roles"] == ["ANALYST", "AUDITOR", "EXECUTOR"]

    ids = [obj["object_id"] for obj in registry["objects"]]
    assert ids == ["GD", "DIR", "WRK"], ids
    print("PASS: BEM-931 v3.6 RM-02 object passports are canonical")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
