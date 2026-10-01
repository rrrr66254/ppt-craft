import json

from deckkit.style import load_style
from helpers import ROOT

PRESETS = sorted(p for p in (ROOT / "presets").iterdir() if (p / "style.json").exists())
SECOND_ORDER_BG = {"#F5F5DC", "#FAF0E6", "#F4F1EA", "#F7F5F0"}


def test_three_presets_exist():
    assert {p.name for p in PRESETS} >= {"report-grid", "keynote-type", "academic-figure"}


def test_presets_valid_and_not_cliche():
    for p in PRESETS:
        st = load_style(p / "style.json")
        assert st["color"]["bg"].upper() not in SECOND_ORDER_BG, p.name
        assert (p / "recipe.md").read_text(encoding="utf-8").strip(), p.name


def test_presets_differ():
    covers = {load_style(p / "style.json")["cover"] for p in PRESETS}
    accents = {load_style(p / "style.json")["color"]["accent"] for p in PRESETS}
    layouts = {load_style(p / "style.json")["layout"] for p in PRESETS}
    assert len(covers) >= 2 and len(accents) == len(PRESETS)
    assert len(layouts) == len(PRESETS)


def test_preset_imagery_differs():
    im = {p.name: load_style(p / "style.json")["imagery"] for p in PRESETS}
    assert len({tuple(v["patterns"]) for v in im.values()}) == len(PRESETS)
    assert im["keynote-type"]["max_bleed"] == 3 and "bleed-scrim" in im["keynote-type"]["patterns"]
    for name in ("academic-figure", "report-grid"):
        assert im[name]["max_bleed"] == 1
    for v in im.values():
        assert "type-only" in v["patterns"] and v["treatment"] == "none" and v["harmonize"] is True


def test_sample_json_has_required_keys():
    s = json.loads((ROOT / "presets" / "_sample.json").read_text(encoding="utf-8"))
    for k in ("title", "claim", "points", "number", "chart", "source", "meta"):
        assert k in s


def _luminance(hex_color):
    def lin(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(int(hex_color[i:i + 2], 16)) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_text_colors_meet_wcag_aa_on_bg():
    for p in PRESETS:
        c = load_style(p / "style.json")["color"]
        for role in ("ink", "muted", "accent"):
            assert _contrast(c[role], c["bg"]) >= 4.5, f"{p.name} {role} {c[role]} on {c['bg']}"


def test_make_thumbs_rejects_unknown_preset(capsys):
    import make_thumbs
    assert make_thumbs.main(["no-such-preset"]) == 1
    assert "report-grid" in capsys.readouterr().err
