#!/usr/bin/env python3
"""Load the verified BEM-934 binding probe with deterministic final-JSON output."""
from pathlib import Path
from urllib.request import urlopen

SOURCE_URL = (
    "https://raw.githubusercontent.com/bereznyi-aleksandr/ai-devops-system/"
    "c7c5fe164bec3d0c1680a3a76e7ce0eb2398f354/"
    "governance/runners/bem934_actions.py"
)
OLD = '        "three-step plan. Commit and push this proof file to main. Do not modify application code, ACTIVE_QUEUE, objects "\n        "registry, or unrelated files."'
NEW = '        "three-step plan. Return exactly the same strict JSON object as your final response with no Markdown fences or "\n        "commentary. You may also commit and push this proof file to main. Do not modify application code, ACTIVE_QUEUE, "\n        "objects registry, or unrelated files."'
source = urlopen(SOURCE_URL, timeout=30).read().decode("utf-8")
if OLD not in source:
    raise RuntimeError("BEM-934 binding task fragment not found")
source = source.replace(OLD, NEW, 1)
compile(source, __file__, "exec")
Path(__file__).write_text(source, encoding="utf-8")
exec(compile(source, __file__, "exec"))
