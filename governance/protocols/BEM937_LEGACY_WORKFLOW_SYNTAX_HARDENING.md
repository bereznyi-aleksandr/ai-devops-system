# BEM-937 Legacy Workflow Syntax Hardening

Created: 2026-06-18T18:36:30Z

## Purpose

Repair invalid legacy BEM-934 GitHub workflow files visible in the Actions UI and install a guard so future sessions do not treat broken workflow YAML as acceptable progress.

## Roadmap

1. `BEM937-P0-LEGACY-WORKFLOW-SYNTAX-REPAIR`
   - rewrite legacy broken workflows into valid manual guard workflows
   - remove inline Python heredocs that caused YAML parse failures
   - remove write permissions from historical guard workflows

2. `BEM937-P1-LEGACY-WORKFLOW-DISPATCH-SMOKE`
   - submit workflow_dispatch for every repaired workflow
   - record API acceptance as smoke evidence

3. `BEM937-P2-WORKFLOW-SYNTAX-GUARD`
   - add `governance/runners/workflow_syntax_guard.py`
   - bind repaired target manifest to a receipt path

4. `BEM937-P3-QUEUE-FINAL-VERIFY`
   - write final verification
   - update ACTIVE_QUEUE to COMPLETE

## Non-claims

The repaired legacy workflows do not promote BEM-934 release state and do not create new product evidence.
They are retained as valid manual historical guards only.
