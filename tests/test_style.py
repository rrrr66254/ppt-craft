import json

import pytest

from deckkit.style import load_style
from helpers import STYLE


def test_defaults_filled():
    st = load_style(STYLE)
    assert st["canvas"]["size"] == pytest.approx((13.333, 7.5), abs=1e-3)
    assert st["canvas"]["title_box"] == [0.6, 0.4, 12.133, 1.1]
    assert st["scale"]["body"] == 18
    assert st["font"]["mono"] == "Malgun Gothic"
    assert st["cover"] == "type" and st["structure"] == "assertion"


def test_partial_section_merges():
    st = load_style({**STYLE, "scale": {"body": 16}})
    assert st["scale"]["body"] == 16 and st["scale"]["title"] == 28


def test_bad_hex_rejected():
    bad = {**STYLE, "color": {**STYLE["color"], "accent": "blue"}}
    with pytest.raises(ValueError, match="color.accent"):
        load_style(bad)


def test_missing_font_rejected():
    with pytest.raises(ValueError, match="font.head"):
        load_style({**STYLE, "font": {"head": "", "body": "X"}})


def test_bad_cover_rejected():
    with pytest.raises(ValueError, match="cover"):
        load_style({**STYLE, "cover": "gradient"})


def test_layout_default_and_validation():
    assert load_style(STYLE)["layout"] == "split"
    assert load_style({**STYLE, "layout": "figure"})["layout"] == "figure"
    with pytest.raises(ValueError, match="layout"):
        load_style({**STYLE, "layout": "masonry"})


def test_input_not_mutated():
    src = {**STYLE, "scale": {"body": 16}}
    load_style(src)
    assert src["scale"] == {"body": 16}


def test_load_from_file(tmp_path):
    p = tmp_path / "style.json"
    p.write_text(json.dumps(STYLE), encoding="utf-8")
    assert load_style(p)["color"]["accent"] == "#1D4E89"


def test_non_dict_section_rejected():
    with pytest.raises(ValueError, match="canvas"):
        load_style({**STYLE, "canvas": None})


def test_tuple_title_box_accepted():
    st = load_style({**STYLE, "canvas": {"title_box": (0.6, 0.4, 10, 1)}})
    assert tuple(st["canvas"]["title_box"]) == (0.6, 0.4, 10, 1)


def test_bool_scale_rejected():
    with pytest.raises(ValueError, match="scale.body"):
        load_style({**STYLE, "scale": {"body": True}})


def test_imagery_defaults():
    im = load_style(STYLE)["imagery"]
    assert im["treatment"] == "none" and im["harmonize"] is True
    assert im["texture"] is None and im["max_bleed"] == 3
    assert "bleed-scrim" in im["patterns"] and "type-only" in im["patterns"]


def test_imagery_unknown_pattern_rejected():
    with pytest.raises(ValueError, match="imagery.patterns"):
        load_style({**STYLE, "imagery": {"patterns": ["split", "collage"]}})
    with pytest.raises(ValueError, match="imagery.patterns"):
        load_style({**STYLE, "imagery": {"patterns": []}})


def test_imagery_texture_validation():
    ok = load_style({**STYLE, "imagery": {"texture": {"kind": "paper", "opacity": 0.06}}})
    assert ok["imagery"]["texture"]["kind"] == "paper"
    with pytest.raises(ValueError, match="imagery.texture"):
        load_style({**STYLE, "imagery": {"texture": {"kind": "paper", "opacity": 0.2}}})
    with pytest.raises(ValueError, match="imagery.texture"):
        load_style({**STYLE, "imagery": {"texture": {"kind": "marble", "opacity": 0.05}}})


def test_imagery_max_bleed_and_other_fields_rejected():
    with pytest.raises(ValueError, match="imagery.max_bleed"):
        load_style({**STYLE, "imagery": {"max_bleed": True}})
    with pytest.raises(ValueError, match="imagery.max_bleed"):
        load_style({**STYLE, "imagery": {"max_bleed": 21}})
    with pytest.raises(ValueError, match="imagery.treatment"):
        load_style({**STYLE, "imagery": {"treatment": "sepia"}})
    with pytest.raises(ValueError, match="imagery.harmonize"):
        load_style({**STYLE, "imagery": {"harmonize": "yes"}})
    with pytest.raises(ValueError, match="imagery"):
        load_style({**STYLE, "imagery": []})


def test_partial_imagery_keeps_defaults():
    im = load_style({**STYLE, "imagery": {"max_bleed": 1}})["imagery"]
    assert im["max_bleed"] == 1 and im["treatment"] == "none" and "split" in im["patterns"]


def test_imagery_unknown_key_rejected():
    with pytest.raises(ValueError, match="unknown keys"):
        load_style({**STYLE, "imagery": {"max_bleeds": 2}})
