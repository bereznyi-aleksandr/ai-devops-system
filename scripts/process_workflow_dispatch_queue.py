#!/usr/bin/env python3
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path.cwd()
QUEUE = ROOT / "governance/workflow_dispatch_queue"
PROCESSED = ROOT / "governance/workflow_dispatch_processed"
RESULTS = ROOT / "governance/workflow_dispatch_results"

def run(cmd):
    print("$ " + cmd)
    subprocess.run(cmd, shell=True, check=True)

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
        run(f"gh workflow run {workflow} --ref {ref} {flags}")
        result = RESULTS / item.name.replace(".json", "_result.json")
        result.write_text(json.dumps({"status":"DISPATCHED","workflow":workflow,"ref":ref,"inputs":inputs}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        shutil.move(str(item), str(PROCESSED / item.name))
        print("WORKFLOW_DISPATCHED " + workflow)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
