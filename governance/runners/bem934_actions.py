#!/usr/bin/env python3
"""One-shot loader for the BEM-934 workflow diagnostics action."""
from pathlib import Path
from urllib.request import urlopen

SOURCE_URL = (
    "https://raw.githubusercontent.com/bereznyi-aleksandr/ai-devops-system/"
    "e97555d315060d26448ef74c1b0cf030907feaf9/"
    "governance/runners/bem934_actions.py"
)
source = urlopen(SOURCE_URL, timeout=30).read().decode("utf-8")
compile(source, __file__, "exec")
Path(__file__).write_text(sourc, encoding="utf-8")
exec(compile(source, __file__, "exec"))
