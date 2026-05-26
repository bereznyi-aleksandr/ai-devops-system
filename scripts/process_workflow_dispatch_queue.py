#!/usr/bin/env python3
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path.cwd()
QUEUE = ROOT / "governance/workflow_dispatch_queue"
PROCESSED = ROOT / "governance/workflow_dispatch_processed"
RESULTS = ROOT / "governance/workflow_dispatch_results"

def run(cmd, check=False):
    print("$ " + cmd)
    return subprocess.run(cmd, shell=True, text=True, capture_output=True, check=check)

def commit_state():
    run('git config user.name "ai-devops-system"')
    run('git config user.email "actions@users.noreply.github.com"')
    run('git add governance/workflow_dispatch_queue governance/workflow_dispatch_processed governance/workflow_dispatch_results governance/runtime/curator_dispatch || true')
    diff = run('git diff --cached --quiet')
    if diff.returncode != 0:
        run('git commit -m "BEM-866 process workflow dispatch queue"', check=True)
        run('git pull --rebase --autostash origin main')
        run('git push origin HEAD:main', check=True)

def main():
    QUEUE.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    files = sorted(QUEUE.glob("*.json"))
    if not files:
        print("WORKFLOW_DISPATCH_QUEUE_EMPTY")
        return 0
    for item in files:
        data = json.loads(item.read_text(encoding="utf-8"))
        workflow = data.get("workflow")
        ref = data.get("ref", "main")
        inputs = data.get("inputs", {})
        cmd = ["gh", "workflow", "run", workflow, "--ref", ref]
        for key, value in inputs.items():
            cmd.extend(["-f", f"{key}={value}"])
        completed = subprocess.run(cmd, text=True, capture_output=True)
        status = "DISPATCHED" if completed.returncode == 0 else "DISPATCH_FAILED"
        result = RESULTS / item.name.replace(".json", "_result.json")
        result.write_text(json.dumps({
            "status": status,
            "workflow": workflow,
            "ref": ref,
            "inputs": inputs,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "cmd": cmd,
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        shutil.move(str(item), str(PROCESSED / item.name))
        print("WORKFLOW_DISPATCH_RESULT " + status + " " + str(workflow))
    commit_state()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
