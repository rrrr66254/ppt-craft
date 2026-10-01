import colorsys
import json

import pytest
from PIL import Image

import imagefx
from helpers import STYLE
from deckkit.style import load_style


def _sat_mean(im):
    small = im.convert("RGB").resize((8, 8))
    px = [small.getpixel((x, y)) for x in range(8) for y in range(8)]
    return sum(colorsys.rgb_to_hsv(*(c / 255 for c in p))[1] for p in px) / len(px)


def _photo(path, size=(64, 48)):
    im = Image.new("RGB", size)
    im.putdata([(x * 4 % 256, y * 5 % 256, 200) for y in range(size[1]) for x in range(size[0])])
    im.save(path)
    return path


def test_gray_has_equal_channels():
    out = imagefx.gray(Image.new("RGB", (4, 4), (200, 50, 20)))
    r, g, b = out.getpixel((1, 1))
    assert r == g == b


def test_duotone_maps_black_and_white_to_palette():
    im = Image.new("RGB", (2, 1), (0, 0, 0))
    im.putpixel((1, 0), (255, 255, 255))
    out = imagefx.duotone(im, "#112233", "#F0E0D0")
    assert out.getpixel((0, 0)) == pytest.approx((0x11, 0x22, 0x33), abs=2)
    assert out.getpixel((1, 0)) == pytest.approx((0xF0, 0xE0, 0xD0), abs=2)


def test_harmonize_lowers_saturation():
    im = Image.new("RGB", (8, 8), (220, 40, 40))
    assert _sat_mean(imagefx.harmonize(im)) < _sat_mean(im)


def test_tone_darkens_and_desaturates():
    im = Image.new("RGB", (8, 8), (220, 40, 40))
    out = imagefx.tone(im)
    assert _sat_mean(out) < _sat_mean(im) and sum(out.getpixel((0, 0))) < sum(im.getpixel((0, 0)))


@pytest.mark.parametrize("kind", ["paper", "grain", "dots", "grid"])
def test_texture_alpha_capped_and_color_exact(kind):
    t = imagefx.texture(kind, "#336699", 0.06, size=(240, 160))
    assert t.mode == "RGBA" and t.size == (240, 160)
    lo, hi = t.getchannel("A").getextrema()
    assert 0 < hi <= round(0.06 * 255)
    r, g, b, _ = t.split()
    assert r.getextrema() == (0x33, 0x33) and g.getextrema() == (0x66, 0x66) and b.getextrema() == (0x99, 0x99)


def test_texture_is_deterministic():
    a = imagefx.texture("paper", "#000000", 0.05, size=(96, 96), seed=3)
    b = imagefx.texture("paper", "#000000", 0.05, size=(96, 96), seed=3)
    assert a.tobytes() == b.tobytes()


def test_texture_rejects_bad_opacity_and_kind():
    with pytest.raises(ValueError):
        imagefx.texture("paper", "#000000", 0.2)
    with pytest.raises(ValueError):
        imagefx.texture("marble", "#000000", 0.05)


def test_treat_file_writes_new_file_and_keeps_source(tmp_path):
    src = _photo(tmp_path / "p.jpg")
    before = src.read_bytes()
    out = imagefx.treat_file(src, "gray", load_style(STYLE), tmp_path / "treated")
    assert out.name == "p-gray.jpg" and out.exists() and src.read_bytes() == before
    assert len(set(Image.open(out).convert("RGB").getpixel((5, 5)))) <= 2  # gray (JPEG may skew by 1)


def test_treat_file_keeps_alpha_as_png(tmp_path):
    src = tmp_path / "a.png"
    Image.new("RGBA", (16, 16), (200, 30, 30, 90)).save(src)
    out = imagefx.treat_file(src, "harmonize", load_style(STYLE), tmp_path / "t")
    assert out.suffix == ".png" and Image.open(out).mode == "RGBA" and Image.open(out).getpixel((1, 1))[3] == 90


def test_cli_treat_and_duotone_fallback_warning(tmp_path, capsys):
    src = _photo(tmp_path / "p.jpg")
    close = {**STYLE, "color": {**STYLE["color"], "ink": "#777777", "bg": "#888888"}}
    sp = tmp_path / "style.json"
    sp.write_text(json.dumps(close), encoding="utf-8")
    rc = imagefx.main(["treat", str(src), "--mode", "duotone", "--style", str(sp), "--out", str(tmp_path / "o")])
    cap = capsys.readouterr()
    assert rc == 0 and "[imagefx] warning: duotone colors too close; using gray" in cap.err
    assert (tmp_path / "o" / "p-duotone.jpg").exists()


def test_cli_texture(tmp_path):
    sp = tmp_path / "style.json"
    sp.write_text(json.dumps(STYLE), encoding="utf-8")
    out = tmp_path / "tex" / "paper.png"
    assert imagefx.main(["texture", "--kind", "paper", "--opacity", "0.06", "--style", str(sp), "--out", str(out)]) == 0
    assert Image.open(out).mode == "RGBA"


def test_cli_exit_codes(tmp_path, capsys):
    sp = tmp_path / "style.json"
    sp.write_text(json.dumps(STYLE), encoding="utf-8")
    assert imagefx.main(["treat", str(tmp_path / "missing.jpg"), "--mode", "gray", "--style", str(sp), "--out", str(tmp_path / "o")]) == 1
    assert imagefx.main(["texture", "--kind", "paper", "--opacity", "0.5", "--style", str(sp), "--out", str(tmp_path / "x.png")]) == 2
    with pytest.raises(SystemExit) as e:
        imagefx.main(["treat"])
    assert e.value.code == 2
