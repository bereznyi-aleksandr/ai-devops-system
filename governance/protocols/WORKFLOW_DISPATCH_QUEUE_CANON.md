# BEM-637 | Workflow Dispatch Queue Canon

Дата: 2026-05-18 | 07:49 (UTC+3)

Problem: commits made by GitHub Actions with GITHUB_TOKEN may not cascade into push-triggered workflows. Operational proof workflows must be launched by workflow_dispatch through a dispatch queue runner using AI_SYSTEM_GITHUB_PAT when available.

Queue path: `governance/workflow_dispatch_queue/*.json`.
