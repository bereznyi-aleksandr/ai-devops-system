#!/usr/bin/env python3
import json
import os
from pathlib import Path
SEP = bytes.fromhex("0a").decode("ascii")
OUT = Path("governance/provider_gates/bem608_claude_primary_provider_gate_result.json")
REPORT = Path("governance/reports/bem608_claude_primary_provider_gate_result.md")
def truth(value):
    return bool(str(value or "").strip())
has_claude = truth(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"))
has_anthropic = truth(os.environ.get("ANTHROPIC_API_KEY"))
status = "primary_candidate_secret_present" if has_claude else "primary_not_proven"
selected = "claude_code_candidate" if has_claude else "gpt_reserve"
reserve_used = False if has_claude else True
reason = "CLAUDE_CODE_OAUTH_TOKEN is present. Primary provider is candidate, but runtime/limits still require Claude smoke response." if has_claude else "Claude primary runtime not proven by this gate; using reserve unless Claude audit response appears."
result = {
  "schema_version": "provider_gate_result.v1",
  "bem": "BEM-605",
  "gate_id": "bem608_claude_primary_provider_gate",
  "provider_checked": True,
  "primary_provider": "claude_code",
  "reserve_provider": "gpt_python_executor",
  "selected_provider": selected,
  "reserve_used": reserve_used,
  "has_claude_code_oauth_token": has_claude,
  "has_anthropic_api_key": has_anthropic,
  "reason": reason,
  "proof_file": str(OUT),
  "checked_at": "workflow_runtime",
  "status": status,
  "blocker": None
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + SEP, encoding="utf-8")
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text("# BEM-608 | Claude Primary Provider Gate Result" + SEP + SEP + "Status: " + status + SEP + "Selected provider: " + selected + SEP + "Reserve used: " + str(reserve_used) + SEP + "Claude Code token present: " + str(has_claude) + SEP + "Anthropic key present: " + str(has_anthropic) + SEP + SEP + "Secrets were not printed." + SEP, encoding="utf-8")
print(json.dumps({"status": status, "selected_provider": selected, "reserve_used": reserve_used}, ensure_ascii=False))
