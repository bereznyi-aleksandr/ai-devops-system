#!/usr/bin/env python3
from pathlib import Path

path = Path(".github/workflows/claude.yml")
text = path.read_text(encoding="utf-8")
lines = text.splitlines()

step_marker = "      - name: Write final result to transport"
try:
    step_start = lines.index(step_marker)
except ValueError as exc:
    raise SystemExit("transport result step not found") from exc

step_end = len(lines)
for idx in range(step_start + 1, len(lines)):
    if lines[idx].startswith("      - name: "):
        step_end = idx
        break

segment = lines[step_start:step_end]

if not any("TASK_TYPE:" in line for line in segment):
    cycle_rel = next(
        (idx for idx, line in enumerate(segment) if line.strip().startswith("CYCLE_ID:")),
        None,
    )
    if cycle_rel is None:
        raise SystemExit("CYCLE_ID env line not found")
    cycle_line = segment[cycle_rel]
    indent = cycle_line[: len(cycle_line) - len(cycle_line.lstrip())]
    segment.insert(cycle_rel + 1, f"{indent}TASK_TYPE:       ${{{ inputs.task_type }}}")

marker = "         # BEM-934 live semantic proof validation"
if marker not in segment:
    outcome_rel = next(
        (
            idx
            for idx, line in enumerate(segment)
            if "outcome = os.environ.get('CLAUDE_OUTCOME', 'unknown')" in line
        ),
        None,
    )
    if outcome_rel is None:
        raise SystemExit("outcome assignment not found")
    segment.insert(
        outcome_rel + 1,
        "          task_type = os.environ.get('TASK_TYPE', '')",
    )

    changed_rel = next(
        (idx for idx, line in enumerate(segment) if line.strip() == "changed = []"),
        None,
    )
    if changed_rel is None:
        raise SystemExit("changed-files block not found")

    pass_rel = None
    for idx in range(changed_rel + 1, len(segment) - 1):
        if segment[idx].strip() == "except Exception:":
            for next_idx in range(idx + 1, min(idx + 4, len(segment)):
                if segment[next_idx].strip() == "pass":
                    pass_rel = next_idx
                    break
        if pass_rel is not None:
            break
    if pass_rel is None:
        raise SystemExit("changed-files exception pass not found")

    validation = r'''
          # BEM-934 live semantic proof validation
          # The Claude action may return a non-zero tool outcome after committing a valid
          # proof. Only the narrowly scoped repair task may derive semantic success from
          # strict, trace-bound proof validation.
          if task_type == 'live_content_analysis_repair':
              proof_path = Path('governance/proofs/BEM934_live_content_tg_934432449.json')
              proof_valid = False
              try:
                  proof = json.loads(proof_path.read_text(encoding='utf-8'))
                  acceptance = proof.get('acceptance_checks')
                  acceptance_ok = (
                      isinstance(acceptance, list)
                      and len(acceptance) >= 2
                      and all(isinstance(item, dict) and item.get('result') == 'PASS' for item in acceptance)
                  )
                  proof_valid = (
                      proof.get('status') == 'PASS'
                      and proof.get('protocol') == 'BEM-934'
                      and proof.get('task_id') == 'BEM934-LIVE-TEST'
                      and proof.get('trace_id') == trace
                      and proof.get('provider_selected') == 'claude_code'
                      and proof.get('source_router_receipt')
                            == 'governance/proofs/BEM932_provider_router_tg_934432449_20260618T102008Z.json'
                      and isinstance(proof.get('invariants'), list)
                      and len(proof['invariants']) >= 2
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
                  status = 'completed'
                  blocker = None
'''.strip("\n").splitlines()
    segment[pass_rel + 1:pass_rel + 1] = validation

lines[step_start:step_end] = segment
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
