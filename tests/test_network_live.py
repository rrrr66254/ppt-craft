"""Live network checks: skipped unless PPTC_NETWORK=1 (they hit real services and AI Horde takes ~30-90 s)."""
import json
import os

import pytest
from PIL import Image

import assets

pytestmark = pytest.mark.skipif(os.environ.get("PPTC_NETWORK") != "1", reason="set PPTC_NETWORK=1 to run live network tests")


def test_iconify_search_and_get(tmp_path, capsys):
    assert assets.main(["icon", "search", "database", "--limit", "5", "--sets", "lucide,tabler"]) == 0
    first = capsys.readouterr().out.splitlines()[0].split()[0]
    assert assets.main(["icon", "get", first, "--color", "#336699", "--out", str(tmp_path / "assets" / "icons"),
                        "--size", "128"]) == 0
    prefix, name = first.split(":")
    assert Image.open(tmp_path / "assets" / "icons" / f"{prefix}-{name}.png").size == (128, 128)


def test_horde_keyless_generation():
    data, model = assets.PROVIDERS["horde"]("a wooden desk with a notebook, natural light", 512, 320, 7, {})
    im = assets._fit(data, 512, 320)
    assert im.width <= 512 and im.height <= 320 and model


def test_openverse_returns_candidates_despite_unreliable_widths(tmp_path, capsys):
    out = tmp_path / "assets" / "_cand"
    assert assets.main(["photo", "search", "planet", "--sources", "openverse", "--n", "4", "--out", str(out)]) == 0
    records = json.loads((out / "candidates.json").read_text(encoding="utf-8"))
    assert len(records) >= 1 and all(r["source"] == "openverse" for r in records)
