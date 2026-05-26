# BEM-866 claude.yml result
Status: DISPATCH_FAILED
Queue exists: False
Processed exists: True
Result exists: True
Claude write OK: False

Result text:
{
  "status": "DISPATCH_FAILED",
  "workflow": "claude.yml",
  "ref": "main",
  "inputs": {
    "role_provider": "claude",
    "trace_id": "bem865_claude_write_selftest",
    "cycle_id": "bem865",
    "task_type": "audit_write_selftest",
    "task": "BEM-865 Claude write selftest. Read governance/tasks/pending/CLAUDE_WRITE_SELFTEST_BEM865.md. Write governance/audit/mailbox/from_claude/BEM865_CLAUDE_WRITE_SELFTEST_RESPONSE.md with exactly: Status: CLAUDE_WRITE_OK. Do not write issue comments."
  },
  "returncode": 1,
  "stdout": "",
  "stderr": "could not create workflow dispatch event: HTTP 422: Unexpected inputs provided: [\"role_provider\"] (https://api.github.com/repos/bereznyi-aleksandr/ai-devops-system/actions/workflows/267324796/dispatches)\n",
  "cmd": [
    "gh",
    "workflow",
    "run",
    "claude.yml",
    "--ref",
    "main",
    "-f",
    "role_provider=claude",
    "-f",
    "trace_id=bem865_claude_write_selftest",
    "-f",
    "cycle_id=bem865",
    "-f",
    "task_type=audit_write_selftest",
    "-f",
    "task=BEM-865 Claude write selftest. Read governance/tasks/pending/CLAUDE_WRITE_SELFTEST_BEM865.md. Write governance/audit/mailbox/from_claude/BEM865_CLAUDE_WRITE_SELFTEST_RESPONSE.md with exactly: Status: CLAUDE_WRITE_OK. Do not write issue comments."
  ]
}

