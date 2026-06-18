#!/usr/bin/env python3
from pathlib import Path

path = Path(".github/workflows/claude.yml")
text = path.read_text(encoding="utf-8")

old_proof = "              proof_path = Path('governance/proofs/BEM934_live_content_tg_934432449.json')"
new_proof = "\n".join(
    [
        "              safe_trace = ''.join(ch if ch.isalnum() or ch in ('_', '-') else '_' for ch in trace)",
        "              proof_path = Path('governance/proofs/BEM934_live_content_' + safe_trace + '.json')",
        "              if not proof_path.exists() and trace == 'tg_934432449_20260618T102008Z'",
        ":                  proof_path = Path('governance/proofs/BEM934_live_content_tg_934432449.json')",
    ]
)
if old_proof not in text and new_proof not in text:
    raise SystemExit("proof path anchor not found")
if old_proof in text:
    text = text.replace(old_proof, new_proof, 1)

old_router = "                        == 'governance/proofs/BEM932_provider_router_tg_934432449_20260618T102008Z.json'"
new_router = "                        == 'governance/proofs/BEM932_provider_router_' + trace + '.json'"
if old_router not in text and new_router not in text:
    raise SystemExit("router receipt anchor not found")
if old_router in text:
    text = text.replace(old_router, new_router, 1)

path.write_text(text, encoding="utf-8")
