import json
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
INDEX_GUARD = ROOT / 'governance' / 'scripts' / 'system_task_index_guarded_v1.py'
INDEX_VALIDATOR = ROOT / 'governance' / 'scripts' / 'system_validate_index_v1.py'
APPLY_RESULT = ROOT / 'governance' / 'scripts' / 'system_apply_result_v1.py'

NO_RESULT_MARKERS = [
    'No known result manifests found in governance/runtime/results',
    'No valid result manifests found in governance/runtime/results',
]


def run_step(title: str, script: Path):
    print(f'=== {title} ===')
    proc = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
    )
    if proc.stdout:
        print(proc.stdout, end='')
    if proc.stderr:
        print(proc.stderr, end='', file=sys.stderr)
    return proc


def main() -> int:
    proc = run_step('INDEX GUARD', INDEX_GUARD)
    if proc.returncode != 0:
        return proc.returncode

    proc = run_step('INDEX VALIDATOR', INDEX_VALIDATOR)
    if proc.returncode != 0:
        return proc.returncode

    proc = run_step('APPLY RESULT', APPLY_RESULT)
    if proc.returncode == 0:
        return 0

    combined = ((proc.stdout or '') + '\n' + (proc.stderr or '')).strip()
    if any(marker in combined for marker in NO_RESULT_MARKERS):
        print(json.dumps({
            'system_apply_result_guarded_version': 'v2',
            'result': 'NO_RESULT',
            'message': 'No result manifests available; apply step skipped',
        }, ensure_ascii=False, indent=2))
        return 0

    return proc.returncode


if __name__ == '__main__':
    raise SystemExit(main())
