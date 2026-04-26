import json
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
LOCK_PATH = ROOT / 'governance' / 'runtime' / '.entrypoint.lock'
INDEX_CONSISTENCY = ROOT / 'governance' / 'scripts' / 'system_index_consistency_check_v1.py'
SAFE_RUNNER = ROOT / 'governance' / 'scripts' / 'system_safe_runner_v1.py'
INVALID_WATCHDOG = ROOT / 'governance' / 'scripts' / 'system_invalid_task_watchdog_v1.py'
NOTIFY = ROOT / 'governance' / 'scripts' / 'system_role_notify_v1.py'
WATCHDOG = ROOT / 'governance' / 'scripts' / 'system_terminal_watchdog_v1.py'
STALLED_WATCHDOG = ROOT / 'governance' / 'scripts' / 'system_stalled_task_watchdog_v1.py'
APPLY_GUARDED = ROOT / 'governance' / 'scripts' / 'system_apply_result_guarded_v1.py'


def run_step(title: str, script: Path) -> int:
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
    return proc.returncode


def acquire_lock() -> bool:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_PATH.exists():
        return False
    payload = {
        'system_entrypoint_lock_version': 'v1',
        'pid': 'LOCAL',
        'lock_path': str(LOCK_PATH.relative_to(ROOT)),
    }
    LOCK_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return True


def release_lock() -> None:
    LOCK_PATH.unlink(missing_ok=True)


def main() -> int:
    dry_run = '--dry-run' in sys.argv[1:]

    if dry_run:
        print(json.dumps({
            'system_entrypoint_version': 'v5',
            'result': 'DRY_RUN',
            'steps': [
                'INDEX CONSISTENCY BOOTSTRAP',
                'SAFE RUNNER',
                'INVALID TASK WATCHDOG',
                'ROLE NOTIFY',
                'TERMINAL WATCHDOG',
                'STALLED TASK WATCHDOG',
                'APPLY RESULT GUARDED',
            ],
            'lock_used': False,
        }, ensure_ascii=False, indent=2))
        return 0

    if not acquire_lock():
        print(json.dumps({
            'system_entrypoint_version': 'v5',
            'result': 'ALREADY_RUNNING',
            'lock_path': str(LOCK_PATH.relative_to(ROOT)),
        }, ensure_ascii=False, indent=2))
        return 0

    try:
        rc = run_step('INDEX CONSISTENCY BOOTSTRAP', INDEX_CONSISTENCY)
        if rc != 0:
            return rc

        rc = run_step('SAFE RUNNER', SAFE_RUNNER)
        if rc != 0:
            return rc

        rc = run_step('INVALID TASK WATCHDOG', INVALID_WATCHDOG)
        if rc != 0:
            return rc

        rc = run_step('ROLE NOTIFY', NOTIFY)
        if rc != 0:
            return rc

        rc = run_step('TERMINAL WATCHDOG', WATCHDOG)
        if rc != 0:
            return rc

        rc = run_step('STALLED TASK WATCHDOG', STALLED_WATCHDOG)
        if rc != 0:
            return rc

        rc = run_step('APPLY RESULT GUARDED', APPLY_GUARDED)
        return rc
    finally:
        release_lock()


if __name__ == '__main__':
    raise SystemExit(main())
