# BEM-607 | Provider Gate Claude Audit Policy

Дата: 2026-05-18 | 06:14 (UTC+3)

## Rule
Before implementation tasks that require Claude primary auditor/executor, the system must record a provider gate result.

## Required fields
- provider_checked
- primary_provider
- reserve_provider
- selected_provider
- reserve_used
- reason
- proof_files
- checked_at

## Current BEM-605 state
Claude audit request exists in mailbox. Implementation remains blocked until Claude response or explicit fallback policy chooses GPT reserve.
