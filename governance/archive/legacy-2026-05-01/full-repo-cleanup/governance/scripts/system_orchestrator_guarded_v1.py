import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
VALIDATOR = ROOT / 'governance' / 'scripts' / 'system_validate_index_v1.py'
ORCHESTRATOR = ROOT / 'governance' / 'scripts' / 'system_orchestrator_v2.py'

def main() -> int:
    validator = subprocess.run(
        [sys.executable, str(VALIDATOR)],
        capture_output=True,
        text=True
    )

    if validator.stdout:
        print(validator.stdout, end='')

    if validator.returncode != 0:
        return validator.returncode

    orchestrator = subprocess.run(
        [sys.executable, str(ORCHESTRATOR)],
        capture_output=True,
        text=True
    )

    if orchestrator.stdout:
        print(orchestrator.stdout, end='')
    if orchestrator.stderr:
        print(orchestrator.stderr, end='', file=sys.stderr)

    return orchestrator.returncode

if __name__ == "__main__":
    raise SystemExit(main())
