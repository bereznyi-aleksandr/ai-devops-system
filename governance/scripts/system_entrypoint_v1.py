import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()

SAFE_RUNNER = ROOT / 'governance' / 'scripts' / 'system_safe_runner_v1.py'
APPLY_GUARDED = ROOT / 'governance' / 'scripts' / 'system_apply_result_guarded_v1.py'

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
    rc = run_step("SAFE RUNNER", SAFE_RUNNER)
    if rc != 0:
        return rc

    rc = run_step("APPLY RESULT GUARDED", APPLY_GUARDED)
    return rc

if __name__ == "__main__":
    raise SystemExit(main())
