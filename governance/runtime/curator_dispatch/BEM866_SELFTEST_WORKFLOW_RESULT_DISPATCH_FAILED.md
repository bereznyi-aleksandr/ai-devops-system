# BEM-866 selftest workflow result
Status: DISPATCH_FAILED
Queue exists: False
Processed exists: True
Result exists: True
Claude write OK: False

Result text:
{
  "status": "DISPATCH_FAILED",
  "workflow": "claude_write_selftest.yml",
  "ref": "main",
  "inputs": {
    "trace_id": "bem865_claude_write_selftest"
  },
  "returncode": 1,
  "stdout": "",
  "stderr": "could not create workflow dispatch event: HTTP 422: Workflow does not have 'workflow_dispatch' trigger (https://api.github.com/repos/bereznyi-aleksandr/ai-devops-system/actions/workflows/283334596/dispatches)\n",
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


Response text:
# BEM-865 CLAUDE WRITE SELFTEST RESPONSE
Status: PENDING_CLAUDE_WRITE_TEST

