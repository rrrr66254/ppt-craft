import json
import re

import lint
from helpers import ROOT, STYLE


def test_api_example_runs_and_is_clean(tmp_path, monkeypatch):
    doc = (ROOT / "skills" / "deck-build" / "deckkit-api.md").read_text(encoding="utf-8")
    code = re.search(r"## Example build.py\s+```python\n(.*?)```", doc, re.S).group(1)
    (tmp_path / "style.json").write_text(json.dumps(STYLE), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    exec(compile(code, "build.py", "exec"), {"__name__": "__main__"})
    res = lint.lint(tmp_path / "out.pptx", style=tmp_path / "style.json")
    assert [f for f in res["findings"] if f["severity"] in ("blocker", "major")] == []
