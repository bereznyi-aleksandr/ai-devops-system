# BEM-866 codex queue block
Indexes: [427, 440, 443, 445, 475]

420:           (result_dir / (trace + '.md')).write_text('\n'.join(lines) + '\n')
421:           print('Result written: status=' + status)
422:           PYEOF
423: 
424:       - name: Commit and push everything
425:         if: always()
426:         shell: bash
427:         env:
428:           GH_TOKEN: ${{ secrets.AI_SYSTEM_GITHUB_PAT }}
429:         run: |
430:           git add -A 2>/dev/null || true
431:           if git diff --cached --quiet; then
432:             echo "Nothing to commit"
433:           else
434:             git commit -m "CODEX-RUNNER: trace=${{ inputs.trace_id }} status=${EXEC_STATUS:-unknown}"
435:             git pull --rebase --autostash origin main || true
436:             git push origin HEAD:main
437:             echo "COMMIT_SHA=$(git rev-parse HEAD)" >> "$GITHUB_ENV"
438:             echo "Pushed: $(git rev-parse HEAD)"
439:           fi

---

433:           else
434:             git commit -m "CODEX-RUNNER: trace=${{ inputs.trace_id }} status=${EXEC_STATUS:-unknown}"
435:             git pull --rebase --autostash origin main || true
436:             git push origin HEAD:main
437:             echo "COMMIT_SHA=$(git rev-parse HEAD)" >> "$GITHUB_ENV"
438:             echo "Pushed: $(git rev-parse HEAD)"
439:           fi
440: 
441:       - name: Process workflow dispatch queue
442:         if: always()
443:         env:
444:           GH_TOKEN: ${{ secrets.AI_SYSTEM_GITHUB_PAT }}
445:         run: |
446:           python3 scripts/process_workflow_dispatch_queue.py || true
447: 
448:       - name: Job summary
449:         if: always()
450:         shell: bash
451:         env:
452:           INPUT_TRACE_ID: ${{ inputs.trace_id }}

---

436:             git push origin HEAD:main
437:             echo "COMMIT_SHA=$(git rev-parse HEAD)" >> "$GITHUB_ENV"
438:             echo "Pushed: $(git rev-parse HEAD)"
439:           fi
440: 
441:       - name: Process workflow dispatch queue
442:         if: always()
443:         env:
444:           GH_TOKEN: ${{ secrets.AI_SYSTEM_GITHUB_PAT }}
445:         run: |
446:           python3 scripts/process_workflow_dispatch_queue.py || true
447: 
448:       - name: Job summary
449:         if: always()
450:         shell: bash
451:         env:
452:           INPUT_TRACE_ID: ${{ inputs.trace_id }}
453:         run: |
454:           python3 - <<'PYEOF'
455:           import os

---

438:             echo "Pushed: $(git rev-parse HEAD)"
439:           fi
440: 
441:       - name: Process workflow dispatch queue
442:         if: always()
443:         env:
444:           GH_TOKEN: ${{ secrets.AI_SYSTEM_GITHUB_PAT }}
445:         run: |
446:           python3 scripts/process_workflow_dispatch_queue.py || true
447: 
448:       - name: Job summary
449:         if: always()
450:         shell: bash
451:         env:
452:           INPUT_TRACE_ID: ${{ inputs.trace_id }}
453:         run: |
454:           python3 - <<'PYEOF'
455:           import os
456:           trace  = os.environ.get('INPUT_TRACE_ID', '?')
457:           status = os.environ.get('EXEC_STATUS', 'blocked')

---

468:               ('| Errors | ' + errors + ' |') if errors else '',
469:               '**No issue #31 comments**', '',
470:           ]
471:           with open(os.environ.get('GITHUB_STEP_SUMMARY', '/tmp/s.md'), 'a') as f:
472:               f.write('\n'.join(l for l in lines if l))
473:           PYEOF
474: 
475: # BEM-865 inline workflow dispatch queue marker
476: # Queue processing is handled after task execution by scripts/process_workflow_dispatch_queue.py.
