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


def test_image_slide_snippet_runs_and_is_clean(tmp_path, monkeypatch):
    from PIL import Image
    from deckkit import Deck
    doc = (ROOT / "skills" / "deck-build" / "deckkit-api.md").read_text(encoding="utf-8")
    code = re.search(r"## Image slides\s+```python\n(.*?)```", doc, re.S).group(1)
    (tmp_path / "assets" / "treated").mkdir(parents=True)
    im = Image.new("RGB", (2400, 1600), (40, 46, 54))
    im.paste((200, 180, 150), (1300, 0, 2400, 1600))
    im.save(tmp_path / "assets" / "treated" / "platform-room-harmonize.jpg")
    entry = {"type": "photo", "size": [2400, 1600], "focus": [0.55, 0.1, 0.95, 0.9], "must_keep": None}
    (tmp_path / "assets" / "images.json").write_text(json.dumps({"platform-room.jpg": entry}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    d = Deck(STYLE, lang="en")
    exec(compile(code, "build.py", "exec"), {"d": d})
    res = lint.lint(d.save(tmp_path / "out.pptx"))
    assert [f for f in res["findings"] if f["severity"] in ("blocker", "major")] == []
