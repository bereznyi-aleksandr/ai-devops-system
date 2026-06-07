#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8", errors="replace")

def main() -> int:
    gpt_hosted = read(".github/workflows/gpt-hosted-roles.yml")
    telegram_poll = read(".github/workflows/telegram-poll.yml")
    codex_local = read(".github/workflows/codex-local.yml")
    role_orchestrator = read(".github/workflows/role-orchestrator.yml")
    telegram_outbox = read(".github/workflows/telegram-outbox-dispatch.yml")
    active = "\n".join([telegram_poll, codex_local, role_orchestrator, telegram_outbox])

    assert "ARCHIVED" in gpt_hosted
    assert "disabled" in gpt_hosted.lower()
    assert "No Gemini/OpenAI HTTP API call" in gpt_hosted
    assert "codex-local.yml" in gpt_hosted

    assert "gpt-hosted-roles.yml/dispatches" not in telegram_poll
    assert "codex-local.yml/dispatches" in telegram_poll
    assert "provider" in telegram_poll and "gpt_codex" in telegram_poll

    forbidden = ["GEMINI_API_KEY", "google/generative-ai", "generativelanguage.googleapis.com"]
    for token in forbidden:
        assert token not in active, f"Forbidden active runtime token found: {token}"

    assert "runs-on: [self-hosted, codex-local]" in codex_local
    assert "codex exec" in codex_local
    print("PASS: BEM-931 v3.6 RM-14 legacy runtime archived/disabled")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
