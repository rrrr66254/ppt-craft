import sys

import pytest
from PIL import Image
from pptx import Presentation
from pptx.oxml.ns import qn

import render
from deckkit import Deck
from helpers import STYLE


def _img(tmp_path, size=(3200, 1000), name="p.png", color=(40, 40, 40)):
    p = tmp_path / name
    Image.new("RGB", size, color).save(p)
    return p


def test_background_is_first_shape_tagged_bleed(tmp_path):
    d = Deck(STYLE)
    s = d.slide("Title")
    d.background(s, _img(tmp_path))
    first = list(s.shapes)[0]
    assert first.name == "pc:bleed" and first.shape_type == 13  # PICTURE
    assert (first.left, first.top) == (0, 0)


def test_background_crop_follows_focus(tmp_path):
    d = Deck(STYLE)
    left = d.background(d.slide(None), _img(tmp_path), focus=(0.0, 0.0, 0.2, 1.0))
    right = d.background(d.slide(None), _img(tmp_path), focus=(0.8, 0.0, 1.0, 1.0))
    assert left.crop_left == pytest.approx(0) and left.crop_right > 0.2
    assert right.crop_right == pytest.approx(0) and right.crop_left > 0.2


def test_fourth_background_warns_l24(tmp_path):
    d = Deck({**STYLE, "imagery": {"max_bleed": 3}})
    for _ in range(3):
        d.background(d.slide(None), _img(tmp_path))
    assert not any("L24" in w for w in d.warnings)
    d.background(d.slide(None), _img(tmp_path))
    assert any("L24" in w and "max_bleed (3)" in w for w in d.warnings)


def test_small_background_warns(tmp_path):
    d = Deck(STYLE)
    d.background(d.slide(None), _img(tmp_path, size=(1200, 700)))
    assert any("use split or inset instead" in w for w in d.warnings)


def test_scrim_xml_alpha_and_no_effects():
    d = Deck(STYLE)
    shape = d.scrim(d.slide(None), (1, 1, 4, 2), color="ink", alpha=0.45)
    srgb = shape._element.spPr.find(qn("a:solidFill")).find(qn("a:srgbClr"))
    assert srgb.get("val") == "111111"
    assert [(c.tag, c.get("val")) for c in srgb] == [(qn("a:alpha"), "45000")]
    assert shape._element.spPr.find(qn("a:effectLst")) is not None
    assert shape.name == "pc:scrim"


@pytest.mark.parametrize("alpha", [0.8, 0, -0.1, True, "0.5"])
def test_scrim_alpha_out_of_range_raises(alpha):
    d = Deck(STYLE)
    with pytest.raises(ValueError, match="alpha"):
        d.scrim(d.slide(None), (1, 1, 4, 2), alpha=alpha)


@pytest.mark.skipif(render.detect_backend() != "powerpoint", reason="needs PowerPoint")
def test_scrim_renders_translucent(tmp_path):
    d = Deck({**STYLE, "color": {**STYLE["color"], "ink": "#000000", "bg": "#FFFFFF"}})
    s = d.slide(None, bg="ink")
    d.scrim(s, (0, 0, d.W, d.H), color="bg", alpha=0.5)
    src = d.save(tmp_path / "t.pptx")
    res = render.render(src, tmp_path / "r", width=400)
    px = Image.open(res["slides"][0]).convert("RGB")
    r, g, b = px.getpixel((px.width // 2, px.height // 2))
    assert 110 <= r <= 145 and abs(r - g) <= 3 and abs(g - b) <= 3
