import random

import pytest
from PIL import Image
from pptx.util import Emu

import render
from deckkit import Deck, legibility as L
from deckkit.crop import cover_crop
from helpers import STYLE

EMU = 914400


def _photo(tmp_path, name="p.jpg", size=(2400, 1350), color=(30, 30, 30)):
    p = tmp_path / name
    Image.new("RGB", size, color).save(p)
    return p


def _two_tone(tmp_path, dark=35, light=225, cut=0.55, size=(1600, 900), name="n.png"):
    """Dark left part, light right part: no single text color passes over the 7-column text box without a scrim."""
    img = Image.new("RGB", size, (light,) * 3)
    img.paste((dark,) * 3, (0, 0, round(size[0] * cut), size[1]))
    p = tmp_path / name
    img.save(p)
    return p


def _on_grid(d, x):
    return any(abs(x - d.col(i, n)[0]) < 1e-6 for n in range(1, 13) for i in range(n))


def _inside(d, box):
    x, y, w, h = box
    return x >= 0 and y >= 0 and x + w <= d.W + 1e-6 and y + h <= d.H + 1e-6 and w > 0 and h > 0


def _inches(shape):
    return tuple(v / EMU for v in (shape.left, shape.top, shape.width, shape.height))


def _names(slide):
    return [sh.name for sh in slide.shapes]


def _check_box(d, box):
    assert _inside(d, box) and _on_grid(d, box[0])


@pytest.fixture
def d():
    return Deck(STYLE)


# ---- bleed_panel ----
@pytest.mark.parametrize("side,focus", [("left", None), ("right", None), (None, (0.0, 0.0, 0.3, 1.0))])
def test_bleed_panel_box_tags_and_zorder(d, tmp_path, side, focus):
    s, box = d.pattern("bleed-panel", "Panel title", _photo(tmp_path), side=side, focus=focus)
    _check_box(d, box)
    shapes = list(s.shapes)
    assert [sh.name for sh in shapes][:2] == ["pc:bleed", "pc:panel"]
    assert shapes[2].has_text_frame and shapes[2].text_frame.text == "Panel title"  # background, panel, then text
    px, py, pw, ph = _inches(shapes[1])
    assert py == 0 and ph == pytest.approx(d.H, abs=1e-3)
    on_right = (side or "right") == "right"
    assert (px > 0) == on_right
    assert (box[0] > d.W / 2) == on_right
    assert px - 1e-6 <= box[0] <= px + pw  # text sits inside the panel


def test_bleed_panel_title_inside_panel(d, tmp_path):
    s, box = d.pattern("bleed-panel", "T", _photo(tmp_path), side="left")
    _, panel, title = list(s.shapes)[:3]
    assert panel.left <= title.left and title.left + title.width <= panel.left + panel.width
    assert (title.top + title.height) / EMU <= box[1]


# ---- bleed_scrim ----
def test_bleed_scrim_dark_photo_no_scrim_light_title(d, tmp_path):
    s, box = d.pattern("bleed-scrim", "Quiet dark", _photo(tmp_path), side="left")
    shapes = list(s.shapes)
    assert [sh.name for sh in shapes][0] == "pc:bleed" and len(shapes) == 2  # background + title only
    assert box is None and d.text_color == "bg"
    assert str(shapes[1].text_frame.paragraphs[0].runs[0].font.color.rgb) == "FFFFFF"


def test_bleed_scrim_gray_photo_adds_scrim_with_planned_alpha(d, tmp_path):
    img = _two_tone(tmp_path)
    s, _ = d.pattern("bleed-scrim", "Gray photo", img, side="left")
    names = _names(s)
    assert names[:2] == ["pc:bleed", "pc:scrim"] and len(names) == 3  # bg, scrim, title
    alpha = int(list(s.shapes)[1]._element.spPr.xpath(".//a:alpha/@val")[0]) / 100000
    x, w = d.col(0, 7)
    _, ty, _, th = d.style["canvas"]["title_box"]
    with Image.open(img) as im:
        crop = cover_crop(im.width, im.height, d.W, d.H)
        px = L.region_pixels(im, L.slide_box_to_image_px((x, ty, w, th), (0, 0, d.W, d.H), im.size, crop))
    plan = L.plan(px, STYLE["color"]["ink"], STYLE["color"]["bg"], d.style["scale"]["title"])
    assert not plan["panel"] and alpha == pytest.approx(max(plan["alpha"], 0.35))  # spec 2 floor
    assert d.text_color == plan["text"]


def test_bleed_scrim_falls_back_to_panel_when_palette_cannot_reach_contrast(tmp_path):
    low = {**STYLE, "color": {**STYLE["color"], "ink": "#777777", "bg": "#888888"}}
    d = Deck(low)
    s, box = d.pattern("bleed-scrim", "Mid gray", _photo(tmp_path, color=(128, 128, 128)), side="left")
    assert _names(s)[:2] == ["pc:bleed", "pc:panel"]
    assert any("fails contrast" in w for w in d.warnings)
    _check_box(d, box)


def test_bleed_scrim_many_words_uses_panel(d, tmp_path):
    s, box = d.pattern("bleed-scrim", "Wordy", _photo(tmp_path), words=20)
    assert "pc:panel" in _names(s) and box is not None
    assert d._bleeds == 1 and len(d.prs.slides) == 1  # no stray slide or background from the abandoned scrim
    assert any("20 words" in w for w in d.warnings)


def test_bleed_scrim_unplannable_region_falls_back_to_panel(d, tmp_path, monkeypatch):
    def boom(*a, **k):
        raise ValueError("empty region")
    monkeypatch.setattr(L, "plan", boom)
    s, _ = d.pattern("bleed-scrim", "x", _photo(tmp_path))
    assert "pc:panel" in _names(s) and any("fails contrast" in w for w in d.warnings)


def test_bleed_scrim_with_body_returns_grid_box(d, tmp_path):
    s, box = d.pattern("bleed-scrim", "Short body", _photo(tmp_path), words=8, side="right")
    _check_box(d, box)
    assert box[0] > d.W / 2 - 1


def test_bleed_scrim_samples_exif_normalized_image(d, tmp_path):
    # raw 900x1600 portrait stored sideways (EXIF 6 = rotate): the normalized image is 1600x900
    img = Image.new("RGB", (900, 1600), (30, 30, 30))
    exif = img.getexif()
    exif[0x0112] = 6
    p = tmp_path / "rot.jpg"
    img.save(p, exif=exif)
    s, _ = d.pattern("bleed-scrim", "Rotated", p, side="left")
    assert "pc:panel" not in _names(s)  # planned over the normalized pixels, no crash


# ---- split ----
@pytest.mark.parametrize("focus,text_right", [((0.0, 0.0, 0.3, 1.0), True), ((0.7, 0.0, 1.0, 1.0), False), (None, False)])
def test_split_text_opposite_focus(d, tmp_path, focus, text_right):
    s, box = d.pattern("split", "Split", _photo(tmp_path), focus=focus)
    _check_box(d, box)
    pic = next(sh for sh in s.shapes if sh.name == "pc:split")
    assert _on_grid(d, pic.left / EMU) and _inside(d, _inches(pic))
    assert (box[0] > pic.left / EMU) == text_right


def test_split_ratio_and_tall_image_gets_narrow_part(d, tmp_path):
    s, box = d.pattern("split", "Wide", _photo(tmp_path), ratio=(5, 7), side="left")
    pic = next(sh for sh in s.shapes if sh.name == "pc:split")
    assert pic.width / EMU == pytest.approx(d.col(0, 5)[1])
    s, box = d.pattern("split", "Tall", _photo(tmp_path, "t.jpg", (1000, 1600)), ratio=(8, 4), side="left")
    pic = next(sh for sh in s.shapes if sh.name == "pc:split")
    assert pic.width / EMU == pytest.approx(d.col(0, 4)[1])
    assert box[2] == pytest.approx(d.col(0, 8)[1])


def test_split_bad_ratio(d, tmp_path):
    with pytest.raises(ValueError, match="ratio"):
        d.pattern("split", "x", _photo(tmp_path), ratio=(5, 5))


# ---- inset ----
def test_inset_caption_below_image_and_box(d, tmp_path):
    s, box = d.pattern("inset", "Inset", _photo(tmp_path), caption="Photo: Han, 2026, Seoul")
    pic = next(sh for sh in s.shapes if sh.name == "pc:inset")
    cap = next(sh for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.startswith("Photo:"))
    assert cap.top >= pic.top + pic.height and cap.left == pic.left
    assert _on_grid(d, pic.left / EMU)
    _check_box(d, box)
    assert box[0] > (pic.left + pic.width) / EMU


def test_inset_without_caption_raises(d, tmp_path):
    with pytest.raises(ValueError, match="I13"):
        d.pattern("inset", "x", _photo(tmp_path), caption="  ")
    with pytest.raises(TypeError):
        d.pattern("inset", "x", _photo(tmp_path))


def test_inset_full_span_has_no_content_box(d, tmp_path):
    _, box = d.pattern("inset", "x", _photo(tmp_path), caption="c", span=12)
    assert box is None


# ---- strip ----
@pytest.mark.parametrize("position", ["bottom", "top"])
def test_strip_band_and_box(d, tmp_path, position):
    s, box = d.pattern("strip", "Strip", _photo(tmp_path, size=(4000, 1000)), position=position, height_ratio=0.35)
    pic = next(sh for sh in s.shapes if sh.name == "pc:strip")
    x, y, w, h = _inches(pic)
    assert w == pytest.approx(d.W, abs=1e-3) and h == pytest.approx(d.H * 0.35, abs=1e-3)
    assert (y == 0) == (position == "top")
    _check_box(d, box)
    if position == "top":
        assert box[1] >= y + h - 1e-6
    else:
        assert box[1] + box[3] <= y + 1e-6


def test_strip_too_tall_raises(d, tmp_path):
    with pytest.raises(ValueError, match="height_ratio"):
        d.pattern("strip", "x", _photo(tmp_path), height_ratio=0.5)


# ---- gallery ----
@pytest.mark.parametrize("n", [2, 3, 4])
def test_gallery_n_cells_one_row_same_crop(d, tmp_path, n):
    paths = [_photo(tmp_path, f"g{i}.jpg") for i in range(n)]
    s, box = d.pattern("gallery", "Gallery", paths, captions=[f"c{i}" for i in range(n)])
    pics = [sh for sh in s.shapes if sh.name == "pc:gallery"]
    assert len(pics) == n and box is None
    assert len({(p.top, p.height, p.width) for p in pics}) == 1
    assert all(_on_grid(d, p.left / EMU) and _inside(d, _inches(p)) for p in pics)
    assert [p.left for p in pics] == sorted(p.left for p in pics)


@pytest.mark.parametrize("n", [2, 3, 4])
def test_gallery_hero_is_wider(d, tmp_path, n):
    paths = [_photo(tmp_path, f"g{i}.jpg") for i in range(n)]
    s, _ = d.pattern("gallery", "Gallery", paths, hero=1, captions=["a"] * n)
    pics = [sh for sh in s.shapes if sh.name == "pc:gallery"]
    assert pics[1].width > max(p.width for i, p in enumerate(pics) if i != 1) * 1.9
    assert pics[-1].left + pics[-1].width <= Emu(round((d.W - d.m) * EMU)) + 2


def test_gallery_count_limits(d, tmp_path):
    for n in (0, 1, 5):
        with pytest.raises(ValueError, match="2 to 4"):
            d.pattern("gallery", "x", [_photo(tmp_path, f"{i}.jpg") for i in range(n)])


def test_gallery_without_captions_warns(d, tmp_path):
    d.pattern("gallery", "x", [_photo(tmp_path, "a.jpg"), _photo(tmp_path, "b.jpg")])
    assert any("I13" in w for w in d.warnings)


# ---- shared rules ----
def test_disallowed_pattern_raises_with_allowed_list(tmp_path):
    d = Deck({**STYLE, "imagery": {"patterns": ["split", "type-only"]}})
    with pytest.raises(ValueError, match=r"not allowed by style.imagery.patterns \(\['split', 'type-only'\]\)"):
        d.pattern("bleed-panel", "x", _photo(tmp_path))


def test_unknown_pattern_name(d, tmp_path):
    with pytest.raises(ValueError, match="pattern must be one of"):
        d.pattern("mosaic", "x", _photo(tmp_path))


def test_bleed_count_feeds_l24(tmp_path):
    d = Deck({**STYLE, "imagery": {"max_bleed": 1}})
    d.pattern("bleed-panel", "a", _photo(tmp_path))
    d.pattern("bleed-panel", "b", _photo(tmp_path))
    assert any("L24" in w for w in d.warnings)


# ---- PowerPoint render: spec section 9 ----
@pytest.mark.skipif(render.detect_backend() != "powerpoint", reason="needs PowerPoint")
def test_rendered_bleed_scrim_title_contrast(tmp_path):
    d = Deck(STYLE)
    d.pattern("bleed-scrim", "A quiet sentence over a photo", _two_tone(tmp_path), side="left")
    src = d.save(tmp_path / "t.pptx")
    im = Image.open(render.render(src, tmp_path / "r", width=1600)["slides"][0]).convert("RGB")
    x, w = d.col(0, 7)
    _, ty, _, th = d.style["canvas"]["title_box"]
    k = im.width / d.W
    region = im.crop((round(x * k), round(ty * k), round((x + w) * k), round((ty + th) * k)))
    text = L.hex_rgb(STYLE["color"][d.text_color])
    ratios = sorted(r for r in (L.contrast(text, p) for p in getattr(region, "get_flattened_data", region.getdata)()) if r >= 1.5)  # drop glyph pixels
    assert len(ratios) > 1000 and ratios[len(ratios) // 20] >= 3.0  # 5th percentile of the background
