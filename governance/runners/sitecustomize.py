"""Bridge GitHub Actions GH_TOKEN into the executor's token contract."""
import os

if not os.environ.get("GITHUB_TOKEN") and os.environ.get("GH_TOKEN"):
    os.environ["GITHUB_TOKEN"] = os.environ["GH_TOKEN"]
