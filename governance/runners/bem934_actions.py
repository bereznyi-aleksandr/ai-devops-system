#!/usr/bin/env python3
"""One-shot loader for the verified BEM-934 proof-bearing binding probe."""
from pathlib import Path
from urllib.request import urlopen

SOURCE_URL = (
    "https://raw.githubusercontent.com/bereznyi-aleksandr/ai-devops-system/"
    "c7c5fe164bec3d0c1680a3a76e7ce0eb2398f354/"
    "governance/runners/bem934_actions.py"
)
source = urlopen(SOURCE_URL, timeout=30).read().decode("utf-8")
compile(source, __file__, "exec")
Path(__file__).write_text(source, encoding="utf-8")
exec(compile(source, __file__, "exec"))
