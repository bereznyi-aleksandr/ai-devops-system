import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()

INDEX_GUARD = ROOT / 'governance' / 'scripts' / 'system_task_index_guarded_v1.py'
INDEX_VALIDATOR = ROOT / 'governance' / 'scripts' / 'system_validate_index_v1.py'
ORCHESTRATOR_GUARDED = ROOT / 'governance' / 'scripts' / 'system_orchestrator_guarded_v1.py'

def run_step(title: str, script: Path) -> int:
    print(f"=== {title} ===")
    proc = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True
    )
    if proc.stdout:
        print(proc.stdout, end='')
    if proc.stderr:
        print(proc.stderr, end='', file=sys.stderr)
    return proc.returncode

def main() -> int:
    rc = run_step("INDEX GUARD", INDEX_GUARD)
    if rc != 0:
        return rc

    rc = run_step("INDEX VALIDATOR", INDEX_VALIDATOR)
    if rc != 0:
        return rc

    rc = run_step("GUARDED ORCHESTRATOR", ORCHESTRATOR_GUARDED)
    return rc

if __name__ == "__main__":
    raise SystemExit(main())
