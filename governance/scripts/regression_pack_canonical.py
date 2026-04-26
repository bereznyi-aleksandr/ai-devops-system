#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
SOURCE_SCRIPTS = ROOT / "governance" / "scripts"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def old_ts(days: int = 3) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, data: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_py(work: Path, script_name: str, *args: str) -> subprocess.CompletedProcess[str]:
    script = work / "governance" / "scripts" / script_name
    return subprocess.run([sys.executable, str(script), *args], cwd=work, text=True, capture_output=True)


def make_workdir() -> tempfile.TemporaryDirectory[str]:
    td = tempfile.TemporaryDirectory(prefix="bem341_regression_")
    work = Path(td.name)
    (work / "governance").mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE_SCRIPTS, work / "governance" / "scripts")
    return td


def seed_task(work: Path, task_id: str, **overrides: object) -> Path:
    data: Dict[str, object] = {
        "task_id": task_id,
        "current_state": "PLAN_APPROVED",
        "last_event_id": f"SEED::{task_id}",
        "last_parent_event_id": "",
        "last_event_type": "PLAN_DECISION",
        "last_actor_role": "AUDITOR",
        "last_event_ts": utc_now(),
        "last_summary": "seed task",
        "next_role": "EXECUTOR",
        "next_action": "IMPLEMENT_TASK",
        "latest_artifact_ref": "",
        "latest_commit_sha": "",
        "latest_result_role": "",
        "latest_result_manifest": "",
        "latest_result_value": "",
        "latest_result_ts": "",
        "error_class": "",
        "error_details": "",
        "last_failure_ts": "",
        "last_failure_from_state": "",
        "stall_count": 0,
        "is_terminal": False,
        "terminal_reason": "",
        "closed_by_system": False,
        "events": [],
        "parent_task_id": "",
        "superseded_by_task_id": "",
    }
    data.update(overrides)
    path = work / "governance" / "runtime" / "tasks" / f"{task_id}.json"
    write_json(path, data)
    return path


def rebuild_index(work: Path) -> None:
    proc = run_py(work, "system_index_consistency_check_v1.py")
    if proc.returncode != 0:
        raise AssertionError(f"index rebuild failed: stdout={proc.stdout} stderr={proc.stderr}")


def stdout_json(proc: subprocess.CompletedProcess[str]) -> Dict[str, object]:
    text = (proc.stdout or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        best: Dict[str, object] = {}
        for idx, ch in enumerate(text):
            if ch != "{":
                continue
            try:
                obj, _end = decoder.raw_decode(text[idx:])
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                best = obj
        return best


def r01_duplicate_index_guard() -> None:
    with make_workdir() as td:
        work = Path(td)
        write_json(work / "governance" / "runtime" / "tasks" / "index.json", {"items": [{"task_id": "DUP"}, {"task_id": "DUP"}]})
        proc = run_py(work, "system_task_index_guarded_v1.py")
        if proc.returncode == 0 or "duplicate task_id entries detected" not in proc.stdout:
            raise AssertionError(f"duplicate guard failed: stdout={proc.stdout} stderr={proc.stderr}")


def r02_stale_index_rebuild() -> None:
    with make_workdir() as td:
        work = Path(td)
        seed_task(work, "TASK-R02")
        write_json(work / "governance" / "runtime" / "tasks" / "index.json", {"items": []})
        proc = run_py(work, "system_index_consistency_check_v1.py")
        data = stdout_json(proc)
        idx = read_json(work / "governance" / "runtime" / "tasks" / "index.json")
        ids = [item.get("task_id") for item in idx.get("items", [])]
        if proc.returncode != 0 or data.get("result") != "REBUILT" or "TASK-R02" not in ids:
            raise AssertionError(f"rebuild failed: stdout={proc.stdout} stderr={proc.stderr}")


def r03_guarded_no_result_manifest_not_found() -> None:
    with make_workdir() as td:
        work = Path(td)
        seed_task(work, "TASK-R03")
        rebuild_index(work)
        (work / "governance" / "runtime" / "results").mkdir(parents=True, exist_ok=True)
        proc = run_py(work, "system_apply_result_guarded_v1.py")
        if proc.returncode != 0 or "NO_RESULT" not in proc.stdout:
            raise AssertionError(f"guarded no-result failed: stdout={proc.stdout} stderr={proc.stderr}")


def r04_apply_guarded_retest() -> None:
    with make_workdir() as td:
        work = Path(td)
        seed_task(work, "TASK-R04", current_state="APPROVED", next_role="EXECUTOR", next_action="WRITE_PLAN")
        rebuild_index(work)
        write_json(work / "governance" / "runtime" / "results" / "executor_success.json", {
            "result_manifest_version": "v1",
            "task_id": "TASK-R04",
            "role": "EXECUTOR",
            "result": "SUCCESS",
            "ts_utc": utc_now(),
            "summary": "executor produced plan",
            "produced_artifact_type": "plan",
            "produced_artifact_path": "governance/plans/TASK-R04.md",
        })
        proc = run_py(work, "system_apply_result_guarded_v1.py")
        task = read_json(work / "governance" / "runtime" / "tasks" / "TASK-R04.json")
        if proc.returncode != 0 or task.get("current_state") != "PLAN_PENDING" or task.get("next_role") != "AUDITOR":
            raise AssertionError(f"guarded apply failed: stdout={proc.stdout} stderr={proc.stderr} task={task}")


def r05_failure_path_local() -> None:
    with make_workdir() as td:
        work = Path(td)
        seed_task(work, "TASK-R05")
        rebuild_index(work)
        proc1 = run_py(work, "system_failure_result_writer_v1.py", "EXECUTOR", "TASK-R05", "local failure path", "TEST_FAILURE", "BLOCKED")
        proc2 = run_py(work, "system_apply_result_guarded_v1.py")
        task = read_json(work / "governance" / "runtime" / "tasks" / "TASK-R05.json")
        if proc1.returncode != 0 or proc2.returncode != 0:
            raise AssertionError(f"failure path command failed: {proc1.stdout} {proc1.stderr} {proc2.stdout} {proc2.stderr}")
        if task.get("current_state") != "BLOCKED" or task.get("next_role") != "AUDITOR" or task.get("next_action") != "REVIEW_STALL":
            raise AssertionError(f"bad failure state: {task}")


def r06_supersession_local() -> None:
    with make_workdir() as td:
        work = Path(td)
        seed_task(work, "TASK-R06-OLD", parent_task_id="PARENT-R06", current_state="PLAN_APPROVED")
        seed_task(work, "TASK-R06-NEW", parent_task_id="PARENT-R06", current_state="APPROVED", next_role="EXECUTOR", next_action="WRITE_PLAN")
        rebuild_index(work)
        write_json(work / "governance" / "runtime" / "results" / "executor_success.json", {
            "result_manifest_version": "v1",
            "task_id": "TASK-R06-NEW",
            "role": "EXECUTOR",
            "result": "SUCCESS",
            "ts_utc": utc_now(),
            "summary": "new sibling supersedes old sibling",
            "produced_artifact_type": "plan",
            "produced_artifact_path": "governance/plans/TASK-R06-NEW.md",
        })
        proc = run_py(work, "system_apply_result_guarded_v1.py")
        old = read_json(work / "governance" / "runtime" / "tasks" / "TASK-R06-OLD.json")
        if proc.returncode != 0 or old.get("current_state") != "SUPERSEDED" or old.get("superseded_by_task_id") != "TASK-R06-NEW":
            raise AssertionError(f"supersession failed: stdout={proc.stdout} stderr={proc.stderr} old={old}")


def r07_tie_break_equal_ts_system_wins() -> None:
    with make_workdir() as td:
        work = Path(td)
        seed_task(work, "TASK-R07", current_state="COMPLETED", next_role="SYSTEM", next_action="CLOSE_TASK")
        rebuild_index(work)
        results = work / "governance" / "runtime" / "results"
        ts = "2026-04-26T00:00:00Z"
        write_json(results / "a_executor.json", {"task_id": "TASK-R07", "role": "EXECUTOR", "result": "SUCCESS", "ts_utc": ts, "produced_artifact_type": "plan", "produced_artifact_path": "governance/plans/TASK-R07.md"})
        write_json(results / "b_auditor.json", {"task_id": "TASK-R07", "role": "AUDITOR", "result": "SUCCESS", "ts_utc": ts, "reviewed_ref": "governance/decisions/IMPLEMENTATION_COMPLETED-TASK-R07.md"})
        write_json(results / "c_system.json", {"task_id": "TASK-R07", "role": "SYSTEM", "result": "SUCCESS", "ts_utc": ts, "event_type": "SYSTEM_CLOSE_TIMEOUT", "summary": "system wins equal timestamp tie"})
        proc = run_py(work, "system_apply_result_guarded_v1.py")
        task = read_json(work / "governance" / "runtime" / "tasks" / "TASK-R07.json")
        if proc.returncode != 0 or task.get("current_state") != "COMPLETED_CLOSED" or task.get("last_actor_role") != "SYSTEM":
            raise AssertionError(f"tie-break failed: stdout={proc.stdout} stderr={proc.stderr} task={task}")


def r08_max_stall_cycles_exhaustion() -> None:
    with make_workdir() as td:
        work = Path(td)
        seed_task(work, "TASK-R08", last_event_ts=old_ts(), next_role="EXECUTOR", next_action="IMPLEMENT_TASK", stall_count=2)
        rebuild_index(work)
        proc = run_py(work, "system_stalled_task_watchdog_v1.py")
        task = read_json(work / "governance" / "runtime" / "tasks" / "TASK-R08.json")
        if proc.returncode != 0:
            raise AssertionError(f"watchdog failed: stdout={proc.stdout} stderr={proc.stderr}")
        if task.get("current_state") != "BLOCKED" or task.get("error_class") != "STALL_CYCLES_EXHAUSTED" or int(task.get("stall_count", 0)) < 3:
            raise AssertionError(f"stall exhaustion failed: {task}")


def r09_notify_processed_roundtrip() -> None:
    with make_workdir() as td:
        work = Path(td)
        notify = work / "governance" / "runtime" / "notifications" / "executor" / "TASK-R09.notify.json"
        write_json(notify, {"role": "EXECUTOR", "task_id": "TASK-R09", "payload": "roundtrip"})
        proc = run_py(work, "system_notify_mark_processed_v1.py", str(notify.relative_to(work)), "BEM-341")
        processed = list((notify.parent / "processed").glob("TASK-R09.*.notify.json"))
        if proc.returncode != 0 or notify.exists() or len(processed) != 1:
            raise AssertionError(f"notify roundtrip failed: stdout={proc.stdout} stderr={proc.stderr} processed={processed}")
        data = read_json(processed[0])
        if data.get("processed_by") != "BEM-341" or data.get("task_id") != "TASK-R09":
            raise AssertionError(f"processed payload invalid: {data}")


def r10_full_e2e_to_closed() -> None:
    with make_workdir() as td:
        work = Path(td)
        task = {
            "task_id": "TASK-GHA-E2E-001",
            "current_state": "COMPLETED",
            "status_bucket": "AWAITING_SYSTEM",
            "next_role": "SYSTEM",
            "next_action": "CLOSE_TASK",
            "is_terminal": False,
            "closed_by_system": False,
            "events": [{"event_id": "SEED", "role": "AUDITOR", "action": "VERIFY_RESULT", "result": "APPROVED"}],
        }
        write_json(work / "governance" / "current_task.json", task)
        write_json(work / "governance" / "tasks" / "TASK-GHA-E2E-001.json", task)
        proc = run_py(work, "close_task_handler.py")
        out = read_json(work / "governance" / "current_task.json")
        if proc.returncode != 0:
            raise AssertionError(f"close handler failed: stdout={proc.stdout} stderr={proc.stderr}")
        if out.get("current_state") != "CLOSED" or out.get("status_bucket") != "COMPLETED_CLOSED" or out.get("is_terminal") is not True or out.get("closed_by_system") is not True:
            raise AssertionError(f"E2E close failed: {out}")


def run() -> Dict[str, object]:
    tests: List[Tuple[str, str, Callable[[], None]]] = [
        ("R-01", "Duplicate index guard", r01_duplicate_index_guard),
        ("R-02", "Stale index rebuild", r02_stale_index_rebuild),
        ("R-03", "Guarded no-result MANIFEST_NOT_FOUND", r03_guarded_no_result_manifest_not_found),
        ("R-04", "Apply guarded retest", r04_apply_guarded_retest),
        ("R-05", "FAILURE path local", r05_failure_path_local),
        ("R-06", "Supersession local", r06_supersession_local),
        ("R-07", "Tie-break equal ts SYSTEM>AUDITOR>EXECUTOR", r07_tie_break_equal_ts_system_wins),
        ("R-08", "Max stall cycles exhaustion stall_count=3", r08_max_stall_cycles_exhaustion),
        ("R-09", "Notify processed roundtrip", r09_notify_processed_roundtrip),
        ("R-10", "Full E2E до CLOSED", r10_full_e2e_to_closed),
    ]
    results = []
    for rid, name, fn in tests:
        try:
            fn()
            results.append({"id": rid, "name": name, "status": "PASS"})
        except Exception as exc:
            results.append({"id": rid, "name": name, "status": "FAIL", "error": str(exc)})
    passed = sum(1 for item in results if item["status"] == "PASS")
    return {"regression_pack": "canonical_functional", "source_tz": "executor_tz_v1.md Section 12", "result": "PASS" if passed == len(results) else "FAIL", "passed": passed, "total": len(results), "tests": results}


if __name__ == "__main__":
    report = run()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["result"] == "PASS" else 1)
