"""Every examples/*/build.py still runs against the current deckkit API and lints clean (no blocker/major)."""
import os
import subprocess
import sys

import pytest

import lint
from helpers import ROOT

BUILDS = sorted((ROOT / "examples").glob("*/build.py"))


def test_examples_exist():
    assert {p.parent.name for p in BUILDS} >= {"business-report", "conference-talk", "research-talk"}


@pytest.mark.parametrize("build", BUILDS, ids=lambda p: p.parent.name)
def test_example_builds_and_lints_clean(build, tmp_path):
    out = tmp_path / "out.pptx"
    r = subprocess.run([sys.executable, str(build), str(out)], capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=300)
    assert r.returncode == 0, r.stderr
    warnings = [line for line in r.stdout.splitlines() if line.startswith("[deckkit warning]")]
    if not any("is not installed" in w for w in warnings):  # text fitting is measured with the real font only
        assert warnings == []
    res = lint.lint(out, style=build.parent / "style.json")
    assert [f for f in res["findings"] if f["severity"] in ("blocker", "major")] == []
