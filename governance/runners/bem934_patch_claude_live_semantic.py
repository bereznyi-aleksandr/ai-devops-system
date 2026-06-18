#!/usr/bin/env python3
from pathlib import Path

path = Path(".github/workflows/claude.yml")
text = path.read_text(encoding="utf-8")

env_anchor = "          CYCLE_ID:        ${{ env.CYCLE_ID }}\n"
task_type_line = "          TASK_TYPE:       ${{ inputs.task_type }}\n"
if task_type_line not in text:
    if env_anchor not in text:
        raise SystemExit("CYCLE_ID env anchor not found")
    text = text.replace(env_anchor, env_anchor + task_type_line, 1)

marker = "          # BEM-934 live semantic proof validation"
outcome_anchor = "          outcome = os.environ.get('CLAUDE_OUTCOME', 'unknown')\n"
validation_block = """          # BEM-934 live semantic proof validation
          task_type = os.environ.get('TASK_TYPE', '')
          if task_type == 'live_content_analysis_repair':
              safe_trace = ''.join(ch if ch.isalnum() or ch in ('_', '-') else '_' for ch in trace)
              proof_path = Path('governance/proofs/BEM934_live_content_' + safe_trace + '.json')
              proof_valid = False
              try:
                  proof = json.loads(proof_path.read_text(encoding='utf-8'))
                  acceptance = proof.get('acceptance_checks')
                  acceptance_ok = (
                      isinstance(acceptance, list)
                      and len(acceptance) >= 2
                      and all(
                          isinstance(item, dict) and item.get('result') == 'PASS'
                          for item in acceptance
                      )
                  )
                  proof_valid = (
                      proof.get('status') == 'PASS'
                      and proof.get('protocol') == 'BEM-934'
                      and proof.get('task_id') == 'BEM934-LIVE-TEST'
                      and proof.get('trace_id') == trace
                      and proof.get('provider_selected') == 'claude_code'
                      and proof.get('source_router_receipt')
                          == 'governance/proofs/BEM932_provider_router_' + trace + '.json'
                      and isinstance(proof.get('invariants'), list)
                      and len(proof['invariants']) == 2
                      and isinstance(proof.get('validation_steps'), list)
                      and len(proof['validation_steps']) >= 2
                      and acceptance_ok
                      and isinstance(proof.get('limitations'), list)
                      and len(proof['limitations']) >= 1
                  )
              except Exception:
                  proof_valid = False
              if proof_valid:
                  outcome = 'success'
"""

if marker not in text:
    if outcome_anchor not in text:
        raise SystemExit("CLAUDE_OUTCOME assignment anchor not found")
    text = text.replace(outcome_anchor, outcome_anchor + validation_block, 1)

path.write_text(text, encoding="utf-8")
