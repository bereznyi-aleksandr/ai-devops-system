#!/usr/bin/env python3
import json
import py_compile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(".")
OUT_JSON = ROOT / "governance/audit/regression-pack-10-latest.json"
OUT_TXT = ROOT / "governance/audit/regression-pack-10-latest.txt"

def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def read_text(path):
    p = ROOT / path
    return p.read_text(encoding="utf-8") if p.exists() else ""

def load_json(path):
    p = ROOT / path
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

def py_ok(path):
    p = ROOT / path
    if not p.exists():
        return False
    try:
        py_compile.compile(str(p), doraise=True)
        return True
    except Exception:
        return False

def contains_all(path, needles):
    text = read_text(path)
    return bool(text) and all(n in text for n in needles)

tests = []

def add(code, name, passed, evidence):
    tests.append({
        "code": code,
        "name": name,
        "passed": bool(passed),
        "evidence": evidence,
    })

current = load_json("governance/current_task.json")
e2e_task = load_json("governance/tasks/TASK-GHA-E2E-001.json")
failure_task = load_json("governance/tasks/TASK-GHA-FAILURE-001.json")
failure_manifest = load_json("governance/failures/TASK-GHA-FAILURE-001.failure.json")

add(
    "R-01",
    "current task JSON is readable",
    bool(current.get("task_id")) and bool(current.get("current_state")),
    f"task_id={current.get('task_id','')}, current_state={current.get('current_state','')}"
)

add(
    "R-02",
    "CLOSE_TASK handler exists and compiles",
    py_ok("governance/scripts/close_task_handler.py"),
    "governance/scripts/close_task_handler.py"
)

add(
    "R-03",
    "FAILURE PATH proof script exists and compiles",
    py_ok("governance/scripts/failure_path_gha_proof.py"),
    "governance/scripts/failure_path_gha_proof.py"
)

add(
    "R-04",
    "dedicated E2E CLOSE_TASK workflow is present",
    contains_all(".github/workflows/e2e-close-task-gha-proof.yml", [
        "workflow_dispatch",
        "python3 governance/scripts/close_task_handler.py",
        "COMPLETED_CLOSED",
        "git push origin main",
    ]),
    ".github/workflows/e2e-close-task-gha-proof.yml"
)

add(
    "R-05",
    "E2E CLOSE_TASK reached CLOSED through GitHub Actions",
    contains_all("governance/audit/BEM-300-check-dedicated-e2e-close-task-gha-result.txt", [
        "run_conclusion=success",
        "current_state=CLOSED",
        "status_bucket=COMPLETED_CLOSED",
        "closed_by_system=true",
        "auditor_task1_e2e_closed=true",
    ]),
    "governance/audit/BEM-300-check-dedicated-e2e-close-task-gha-result.txt"
)

add(
    "R-06",
    "dedicated FAILURE PATH workflow is present",
    contains_all(".github/workflows/failure-path-gha-proof.yml", [
        "workflow_dispatch",
        "python3 governance/scripts/failure_path_gha_proof.py",
        "BLOCKED",
        "REVIEW_STALL",
        "git push origin main",
    ]),
    ".github/workflows/failure-path-gha-proof.yml"
)

add(
    "R-07",
    "FAILURE PATH passed through GitHub Actions",
    contains_all("governance/audit/BEM-303-check-failure-path-gha-result.txt", [
        "run_conclusion=success",
        "current_state=BLOCKED",
        "status_bucket=REVIEW_STALL",
        "next_role=AUDITOR",
        "failure_path_gha_ok=true",
    ]),
    "governance/audit/BEM-303-check-failure-path-gha-result.txt"
)

add(
    "R-08",
    "FAILURE manifest exists and is watchdog-produced",
    failure_manifest.get("producer") == "stalled_watchdog"
    and failure_manifest.get("task_id") == "TASK-GHA-FAILURE-001"
    and failure_manifest.get("failure_path") == "GHA_FAILURE_PATH",
    "governance/failures/TASK-GHA-FAILURE-001.failure.json"
)

failure_events = failure_task.get("events", [])
if not isinstance(failure_events, list):
    failure_events = []

add(
    "R-09",
    "FAILURE task is BLOCKED / REVIEW_STALL / AUDITOR",
    failure_task.get("current_state") == "BLOCKED"
    and failure_task.get("status_bucket") == "REVIEW_STALL"
    and failure_task.get("next_role") == "AUDITOR"
    and len(failure_events) >= 3,
    f"state={failure_task.get('current_state','')}, bucket={failure_task.get('status_bucket','')}, next_role={failure_task.get('next_role','')}, events={len(failure_events)}"
)

e2e_events = e2e_task.get("events", [])
if not isinstance(e2e_events, list):
    e2e_events = []

add(
    "R-10",
    "full E2E cycle includes CLOSED terminal state",
    e2e_task.get("current_state") == "CLOSED"
    and e2e_task.get("status_bucket") == "COMPLETED_CLOSED"
    and e2e_task.get("is_terminal") is True
    and e2e_task.get("closed_by_system") is True
    and len(e2e_events) >= 2,
    f"state={e2e_task.get('current_state','')}, bucket={e2e_task.get('status_bucket','')}, terminal={e2e_task.get('is_terminal')}, closed_by_system={e2e_task.get('closed_by_system')}, events={len(e2e_events)}"
)

passed_count = sum(1 for t in tests if t["passed"])
total_count = len(tests)
all_pass = passed_count == 10 and total_count == 10

result = {
    "pack": "R-01...R-10",
    "created_at": now(),
    "total": total_count,
    "passed": passed_count,
    "failed": total_count - passed_count,
    "all_pass": all_pass,
    "tests": tests,
}

OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "regression pack R-01...R-10",
    f"created_at={result['created_at']}",
    f"total={total_count}",
    f"passed={passed_count}",
    f"failed={total_count - passed_count}",
    f"all_pass={str(all_pass).lower()}",
]
for t in tests:
    status = "PASS" if t["passed"] else "FAIL"
    lines.append(f"{t['code']}={status} | {t['name']} | {t['evidence']}")
OUT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")

print(f"REGRESSION_PACK_10_TOTAL={total_count}")
print(f"REGRESSION_PACK_10_PASSED={passed_count}")
print(f"REGRESSION_PACK_10_FAILED={total_count - passed_count}")
print(f"REGRESSION_PACK_10_RESULT={'PASS' if all_pass else 'FAIL'}")
for t in tests:
    print(f"{t['code']}={'PASS' if t['passed'] else 'FAIL'}")
raise SystemExit(0 if all_pass else 1)
