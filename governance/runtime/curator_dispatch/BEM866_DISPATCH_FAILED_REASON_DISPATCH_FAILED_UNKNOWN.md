# BEM-866 dispatch failed reason
Status: DISPATCH_FAILED_UNKNOWN
Result exists: True

Result text:
{
  "status": "DISPATCH_FAILED",
  "workflow": "claude_internal_auditor_dispatcher.yml",
  "ref": "main",
  "inputs": {
    "trace_id": "bem865_claude_write_selftest",
    "task_path": "governance/tasks/pending/CLAUDE_WRITE_SELFTEST_BEM865.md",
    "response_path": "governance/audit/mailbox/from_claude/BEM865_CLAUDE_WRITE_SELFTEST_RESPONSE.md",
    "expected_status": "CLAUDE_WRITE_OK"
  },
  "error": "Command 'gh workflow run claude_internal_auditor_dispatcher.yml --ref main -f trace_id=bem865_claude_write_selftest -f task_path=governance/tasks/pending/CLAUDE_WRITE_SELFTEST_BEM865.md -f response_path=governance/audit/mailbox/from_claude/BEM865_CLAUDE_WRITE_SELFTEST_RESPONSE.md -f expected_status=CLAUDE_WRITE_OK' returned non-zero exit status 1."
}

