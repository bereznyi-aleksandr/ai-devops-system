#!/usr/bin/env python3
import json
from pathlib import Path
import bem934_objects_bound_repair as repair
import bem934_objects_bound_runner as original

TRACE = "bem934_objects_bound_repair_27751086692_wrk"
EXEC_SHA = "b907bccbb4b18dbd00751f9f1c18ae69ccbc1fa1"
RECEIPT = Path("governance/proofs/BEM934_claude_result_materialization_receipt.json")
PLAN = Path("governance/proofs/BEM934_object_binding_plan.json")
REPORT = Path("governance/reports/bem934_objects_bound_repair_27751086692_wrk.md")
PROOF_DIR = Path("governance/proofs/bem934_objects_bound")
PASSPORT = "governance/architecture/object_passports/WRK.json"


def at(sha: str, path: Path) -> str:
    return repair.git("show", f"{sha}:{path}")


def blob(sha: str, path: Path) -> str:
    return repair.git("rev-parse", f"{sha}:{path}")


def select_stashed(text: str) -> str:
    output = []
    mode = "normal"
    for line in text.splitlines(keepends=True):
        if line.startswith("<<<<<<< "):
            if mode != "normal":
                raise RuntimeError("nested conflict marker")
            mode = "upstream"
            continue
        if line.startswith("=======") and mode == "upstream":
            mode = "stashed"
            continue
        if line.startswith(">>>>>>> ") and mode == "stashed":
            mode = "normal"
            continue
        if mode in {"normal", "stashed"}:
            output.append(line)
    if mode != "normal":
        raise RuntimeError(unterminated conflict marker")
    clean = "".join(output)
    if any(marker in clean for marker in ("<<<<<<<", "=======", ">>>>>>>")):
        raise RuntimeError("conflict marker remained")
    return clean


def main() -> None:
    repair.git("config", "user.email", "bem934-recovery@ai-devops-system")
    repair.git("config", "user.name", "BEM-934 Recovery")
    repair.git("fetch", "origin", "main")
    repair.git("pull", "--rebase", "--autostash", "origin", "main")

    receipt = json.loads(select_stashed(at(EXEC_SHA, RECEIPT)))
    plan = json.loads(select_stashed(at(EXEC_SHA, PLAN)))
    repair.validate_source(receipt, plan, TRACE, "WRK")

    RECEIT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    clean_sha = repair.push_commit(
        "Resolve BEM-934 materialization race with canonical WRK Claude output",
        [str(RECEIPT), str(PLAN)],
    )

    PROOF_DIR.mkdir(parents=True, exist_ok=True)
    wrk_path = PROOF_DIR / "WRK_runtime_binding.json"
    wrk = {
        "status": "PASS",
        "protocol": "BEM-934",
        "task_id": "BEM934-OBJECTS-BOUND",
        "object_id": "WRK",
        "passport_path": PASSPORT,
        "trace_id": TRACE,
        "provider": "claude",
        "workflow": ".github/workflows/claude.yml",
        "source_receipt_path": str(RECEIPT),
        "source_receipt_blob_sha": blob(clean_sha, RECEIPT),
        "source_plan_path": str(PLAN),
        "source_plan_blob_sha": blob(clean_sha, PLAN),
        "source_commit_sha": clean_sha,
        "execution_commit_sha": EXEC_SHA,
        "source_report_path": str(REPORT),
        "source_report_blob_sha": blob(EXEC_SHA, REPORT),
        "race_resolution_commit_sha": clean_sha,
        "receipt": receipt,
        "plan": plan,
    }
    wrk_path.write_text(json.dumps(wrk, ensure_ascii=False, indent=2) + "\n")
    wrk_commit = repair.push_commit(
        "Capture BEM-934 WRK runtime binding evidence",
        [str(wrk_path)],
    )
    wrk["snapshot_commit_sha"] = wrk_commit
    wrk["snapshot_blob_sha"] = repair.git("rev-parse", f"HEAD:{wrk_path}")
    wrk_path.write_text(json.dumps(wrk, ensure_ascii=False, indent=2) + "\n")
    repair.push_commit("Finalize BEM-934 WRK evidence identifiers", [str(wrk_path)])

    evidence = [
        json.loads((PROOF_DIR / f"{object_id}_runtime_binding.json").read_text())
        for object_id in ("GD", "DIR", "WRK")
    ]
    binding_sha = original.write_binding(evidence)
    original.finalize(binding_sha)
    print(json.dumps({
        "status": "PASS",
        "binding_sha": binding_sha,
        "receipt": str(original.FINAL_RECEIPT),
        "next": "BEM934-LIVE-TEST",
    }))


if __name__ == "__main__":
    main()
