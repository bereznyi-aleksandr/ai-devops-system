# BEM-867 compare detail
Name: bem866_result
Path: governance/workflow_dispatch_results/bem865_claude_write_selftest_result.json
Exists: True

Text:
{
  "status": "DISPATCHED",
  "workflow": "claude_write_selftest.yml",
  "ref": "main",
  "inputs": {
    "trace_id": "bem865_claude_write_selftest"
  },
  "returncode": 0,
  "stdout": "https://github.com/bereznyi-aleksandr/ai-devops-system/actions/runs/26443445237\n",
  "stderr": "",
  "cmd": [
    "gh",
    "workflow",
    "run",
    "claude_write_selftest.yml",
    "--ref",
    "main",
    "-f",
    "trace_id=bem865_claude_write_selftest"
  ]
}

