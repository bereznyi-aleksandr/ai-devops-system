# BEM-935 P0 Runtime Foundation Protocol

Created: 2026-06-18T17:40:00Z
Source: EXTERNAL_AUDITOR_CLAUDE detailed audit after BEM-934 closure.

## Goal

Turn the minimum working Telegram -> Claude route into a safer autonomous foundation by replacing critical Python stubs and restoring root startup context.

## P0 tasks

1. `BEM935-P0-ROOT-CONTEXT`
   - create root `AGENT_CONTEXT.md`
   - include current BEM-934 evidence and runtime truth

2. `BEM935-P0-CURATOR-ROUTER`
   - replace 23-byte `governance/runners/curator_router.py`
   - route by `governance/config/provider_config.json`
   - reject disabled/deprecated providers
   - emit proof-bearing provider decisions

3. `BEM935-P0-DISPATCH-CONSUMER`
   - replace 23-byte `governance/runners/dispatch_consumer.py`
   - consume `governance/state/dispatch_queue.jsonl`
   - append planned dispatch records to `governance/state/dispatch_processed.jsonl`
   - write receipt `governance/proofs/BEM935_dispatch_consumer_receipt.json`

## Non-claims

This protocol does not claim full multi-provider autonomy.
It only restores root context, local provider selection, and dispatch queue consumption.
Actual GitHub workflow dispatch remains owned by workflow/webhook layers until separately implemented and audited.
