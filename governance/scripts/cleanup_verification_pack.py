#!/usr/bin/env python3
from __future__ import annotations

import json
import py_compile
from pathlib import Path
from typing import Callable, Dict, List

ROOT = Path(__file__).resolve().parents[2]
GOV = ROOT / "governance"
SCRIPTS = GOV / "scripts"
WORKFLOWS = ROOT / ".github" / "workflows"


def assert_file(path: Path) -> None:
    if not path.exists() or not path.is_file():
        raise AssertionError(f"missing file: {path.relative_to(ROOT)}")


def assert_no_file(path: Path) -> None:
    if path.exists():
        raise AssertionError(f"unexpected active file: {path.relative_to(ROOT)}")


def r01_canonical_scripts_present() -> None:
    required = [
        "system_entrypoint_v1.py",
        "system_safe_runner_v1.py",
        "system_task_index_guarded_v1.py",
        "system_validate_index_v1.py",
        "system_index_consistency_check_v1.py",
        "system_orchestrator_v2.py",
        "system_orchestrator_guarded_v1.py",
        "system_router_v1.py",
        "system_role_notify_v1.py",
        "system_notify_mark_processed_v1.py",
        "system_role_inbox_reader_v1.py",
        "system_role_launcher_v2.py",
        "system_terminal_watchdog_v1.py",
        "system_stalled_task_watchdog_v1.py",
        "system_invalid_task_watchdog_v1.py",
        "system_apply_result_v1.py",
        "system_apply_result_guarded_v1.py",
        "system_result_intake_v1.py",
        "system_failure_result_writer_v1.py",
        "system_ledger_writer_v1.py",
        "system_transition_map_v1.py",
        "system_artifact_classifier_v1.py",
        "system_packet_writer_v1.py",
        "regression_pack_canonical.py",
    ]
    for name in required:
        assert_file(SCRIPTS / name)


def r02_obsolete_scripts_absent() -> None:
    obsolete = [
        "system_orchestrator_v1.py",
        "system_role_launcher_v1.py",
        "regression_pack_10.py",
        "regression_pack_v1.py",
        "autonomy_constants.py",
        "run_executor_codex.sh",
        "run_executor_codex_v2.sh",
        "run_auditor_codex_v1.sh",
        "system_doctor_v1.py",
        "system_health_check_v1.py",
        "system_status_v1.py",
        "system_supersession_v1.py",
    ]
    for name in obsolete:
        assert_no_file(SCRIPTS / name)


def r03_proof_scripts_present() -> None:
    assert_file(SCRIPTS / "close_task_handler.py")
    assert_file(SCRIPTS / "failure_path_gha_proof.py")


def r04_router_single_schema() -> None:
    text = (SCRIPTS / "system_router_v1.py").read_text(encoding="utf-8")
    if "CANONICAL_LEDGER_SCHEMA = \"27-col\"" not in text:
        raise AssertionError("router canonical 27-col marker missing")
    if "14-col" in text:
        raise AssertionError("router still references legacy 14-col schema")


def r05_single_active_protocol() -> None:
    assert_file(GOV / "PROTOCOL.md")
    extras = [p for p in GOV.glob("PROTOCOL*") if p.name != "PROTOCOL.md"]
    if extras:
        raise AssertionError("extra active PROTOCOL files: " + ", ".join(str(p.relative_to(ROOT)) for p in extras))


def r06_v37_prompts_absent() -> None:
    assert_no_file(GOV / "prompts" / "executor_codex_system_prompt_v3_7.txt")
    assert_no_file(GOV / "prompts" / "auditor_codex_system_prompt_v3_7.txt")


def r07_v36_prompts_present() -> None:
    assert_file(GOV / "prompts" / "executor_system_prompt_v3_6_rc2.txt")
    assert_file(GOV / "prompts" / "auditor_system_prompt_v3_6_rc2.txt")


def r08_current_task_clean() -> None:
    path = GOV / "current_task.json"
    assert_file(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "current_state": "APPROVED",
        "next_role": "EXECUTOR",
        "next_action": "IMPLEMENT_TASK",
        "events": [],
    }
    for key, value in expected.items():
        if data.get(key) != value:
            raise AssertionError(f"current_task {key}={data.get(key)!r}, expected {value!r}")


def r09_active_workflows_clean() -> None:
    forbidden = [
        "ledger-writer-v2.yml",
        "executor-runner-v3_6_rc2.yml",
        "auditor-runner-v3_6_rc2.yml",
        "canonical-smoke-cycle-v3_6_rc2.yml",
        "workflow-monitor.yml",
        "request-file-create.yml",
        "ledger-request-ingress.yml",
        "ledger-server-write.yml",
        "analyst-task-writer.yml",
        "analyst-verifier-runner.yml",
        "autonomy-failure-path.yml",
    ]
    for name in forbidden:
        assert_no_file(WORKFLOWS / name)


def r10_python_compile_core_scripts() -> None:
    for path in sorted(SCRIPTS.glob("*.py")):
        py_compile.compile(str(path), doraise=True)


def run() -> Dict[str, object]:
    tests: List[tuple[str, Callable[[], None]]] = [
        ("R-01 canonical scripts present", r01_canonical_scripts_present),
        ("R-02 obsolete scripts absent", r02_obsolete_scripts_absent),
        ("R-03 proof scripts present", r03_proof_scripts_present),
        ("R-04 router single 27-col schema", r04_router_single_schema),
        ("R-05 single active PROTOCOL.md", r05_single_active_protocol),
        ("R-06 v3.7 prompts absent", r06_v37_prompts_absent),
        ("R-07 v3.6-RC2 prompts present", r07_v36_prompts_present),
        ("R-08 current_task clean", r08_current_task_clean),
        ("R-09 active workflows clean", r09_active_workflows_clean),
        ("R-10 core scripts compile", r10_python_compile_core_scripts),
    ]
    results = []
    for test_id, (name, fn) in enumerate(tests, start=1):
        rid = f"R-{test_id:02d}"
        try:
            fn()
            results.append({"id": rid, "name": name, "status": "PASS"})
        except Exception as exc:
            results.append({"id": rid, "name": name, "status": "FAIL", "error": str(exc)})
    passed = sum(1 for item in results if item["status"] == "PASS")
    return {
        "regression_pack": "cleanup_verification",
        "result": "PASS" if passed == len(results) else "FAIL",
        "passed": passed,
        "total": len(results),
        "tests": results,
    }


if __name__ == "__main__":
    report = run()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["result"] == "PASS" else 1)
