#!/usr/bin/env python3
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path.cwd()
QUEUE = ROOT / "governance/workflow_dispatch_queue"
PROCESSED = ROOT / "governance/workflow_dispatch_processed"
RESULTS = ROOT / "governance/workflow_dispatch_results"

def run(cmd, check=True):
    print("$ " + cmd)
    return subprocess.run(cmd, shell=True, check=check)

def commit_state():
    run('git config user.name "ai-devops-system"', check=False)
    run('git config user.email "actions@users.noreply.github.com"', check=False)
    run('git add governance/workflow_dispatch_queue governance/workflow_dispatch_processed governance/workflow_dispatch_results governance/runtime/curator_dispatch || true', check=False)
    diff = run('git diff --cached --quiet', check=False)
    if diff.returncode != 0:
        run('git commit -m "BEM-865 process workflow dispatch queue"')
        run('git push origin HEAD:main')

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
        workflow = data["workflow"]
        ref = data.get("ref", "main")
        inputs = data.get("inputs", {})
        flags = " ".join([f"-f {k}={v}" for k, v in inputs.items()])
        status = "DISPATCH_ATTEMPTED"
        error = None
        try:
            run(f"gh workflow run {workflow} --ref {ref} {flags}")
            status = "DISPATCHED"
        except Exception as exc:
            status = "DISPATCH_FAILED"
            error = str(exc)[:1000]
        result = RESULTS / item.name.replace(".json", "_result.json")
        result.write_text(json.dumps({"status":status,"workflow":workflow,"ref":ref,"inputs":inputs,"error":error}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        shutil.move(str(item), str(PROCESSED / item.name))
        print("WORKFLOW_DISPATCH_RESULT " + status + " " + workflow)
    commit_state()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
