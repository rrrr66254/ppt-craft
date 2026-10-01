import json
import os
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

import images


def test_content_bbox_trims_uniform_border():
    im = Image.new("RGB", (400, 300), "white")
    ImageDraw.Draw(im).rectangle([100, 50, 299, 249], fill="black")
    assert images.content_bbox(im) == pytest.approx([0.25, 0.1667, 0.75, 0.8333], abs=0.01)


def test_content_bbox_full_when_no_border():
    im = Image.frombytes("RGB", (64, 64), os.urandom(64 * 64 * 3))
    assert images.content_bbox(im) == [0.0, 0.0, 1.0, 1.0]


def test_exif_rotation_applied(tmp_path):
    src = tmp_path / "rot.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6  # rotated 90 degrees
    Image.frombytes("RGB", (200, 100), os.urandom(200 * 100 * 3)).save(src, exif=exif)
    info = images.prep(src, tmp_path / "assets")
    assert info["size"] == [100, 200]


def test_large_photo_capped_and_jpeg(tmp_path):
    src = tmp_path / "big.png"
    Image.frombytes("RGB", (4000, 1000), os.urandom(4000 * 1000 * 3)).save(src)
    info = images.prep(src, tmp_path / "assets")
    assert max(info["size"]) == 3000 and info["file"].endswith(".jpg") and info["kind_guess"] == "photo"


def test_screenshot_stays_png(tmp_path):
    src = tmp_path / "shot.png"
    im = Image.new("RGB", (800, 500), "white")
    ImageDraw.Draw(im).rectangle([40, 40, 400, 200], fill=(30, 60, 90))
    im.save(src)
    info = images.prep(src, tmp_path / "assets")
    assert info["file"].endswith(".png") and info["kind_guess"] == "screenshot"


def test_main_merges_and_keeps_focus(tmp_path):
    src = tmp_path / "shot.png"
    Image.new("RGB", (300, 200), "white").save(src)
    out = tmp_path / "assets"
    images.main([str(src), "--out", str(out)])
    index = json.loads((out / "images.json").read_text(encoding="utf-8"))
    index["shot.png"]["focus"] = [0.1, 0.1, 0.5, 0.5]
    (out / "images.json").write_text(json.dumps(index), encoding="utf-8")
    images.main([str(src), "--out", str(out)])
    again = json.loads((out / "images.json").read_text(encoding="utf-8"))
    assert again["shot.png"]["focus"] == [0.1, 0.1, 0.5, 0.5]
    assert again["shot.png"]["must_keep"] is None


def test_prep_never_overwrites_source(tmp_path):
    out = tmp_path / "assets"
    out.mkdir()
    src = out / "same.png"
    Image.new("RGB", (100, 100), "white").save(src)
    before = src.read_bytes()
    info = images.prep(src, out)
    assert src.read_bytes() == before and info["file"] != "same.png"


def test_same_stem_different_sources_keep_both(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    s1, s2 = tmp_path / "a" / "logo.png", tmp_path / "b" / "logo.png"
    Image.new("RGB", (100, 100), "red").save(s1)
    Image.new("RGB", (120, 80), "blue").save(s2)
    out = tmp_path / "assets"
    images.main([str(s1), str(s2), "--out", str(out)])
    images.main([str(s1), str(s2), "--out", str(out)])  # the name does not change on a re-run
    index = json.loads((out / "images.json").read_text(encoding="utf-8"))
    assert sorted(index) == ["logo-2.png", "logo.png"]
    assert index["logo.png"]["size"] == [100, 100] and index["logo-2.png"]["size"] == [120, 80]


def test_cmyk_flat_image_preps_to_png(tmp_path):
    src = tmp_path / "cmyk.tif"
    Image.new("CMYK", (100, 60), (0, 0, 0, 0)).save(src)
    info = images.prep(src, tmp_path / "assets")
    out = Image.open(tmp_path / "assets" / info["file"])
    assert info["file"].endswith(".png") and out.mode in ("RGB", "RGBA")
    assert "icc_profile" not in out.info


def test_cmyk_with_icc_profile_converted_to_srgb_without_cmyk_profile(tmp_path):
    icm = Path(r"C:\Windows\System32\spool\drivers\color\RSWOP.icm")
    if not icm.exists():
        pytest.skip("no CMYK ICC profile")
    src = tmp_path / "cmyk_icc.tif"
    Image.new("CMYK", (100, 60), (255, 0, 0, 0)).save(src, icc_profile=icm.read_bytes())
    info = images.prep(src, tmp_path / "assets")
    out = Image.open(tmp_path / "assets" / info["file"])
    assert out.mode in ("RGB", "RGBA") and "icc_profile" not in out.info
    r, g, b = out.convert("RGB").getpixel((5, 5))
    assert b > r and 100 < g < 230  # result of the profile conversion (a plain conversion would give G=255)


def test_16bit_image_preps(tmp_path):
    src = tmp_path / "deep.png"
    Image.new("I;16", (50, 50), 40000).save(src)
    info = images.prep(src, tmp_path / "assets")
    assert info["size"] == [50, 50] and info["kind_guess"] == "screenshot"


def test_write_json_atomic_keeps_old_file_on_failure(tmp_path, monkeypatch):
    target = tmp_path / "sub" / "x.json"
    images.write_json_atomic(target, {"a": 1})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(images.os, "replace", boom)
    with pytest.raises(OSError):
        images.write_json_atomic(target, {"a": 2})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}
    assert [p.name for p in target.parent.iterdir()] == ["x.json"]  # no leftover temp file


def test_write_json_atomic_unserializable_leaves_no_temp(tmp_path):
    with pytest.raises(TypeError):
        images.write_json_atomic(tmp_path / "y.json", {"a": object()})
    assert list(tmp_path.iterdir()) == []


def test_big_noisy_rgb_png_becomes_jpeg_and_is_much_smaller(tmp_path):
    src = tmp_path / "big_noise.png"
    Image.frombytes("RGB", (2000, 1500), os.urandom(2000 * 1500 * 3)).save(src)
    info = images.prep(src, tmp_path / "assets")
    assert info["file"].endswith(".jpg") and info["kind_guess"] == "photo"
    assert (tmp_path / "assets" / info["file"]).stat().st_size < src.stat().st_size


def _flat_big(tmp_path):
    src = tmp_path / "smooth.png"
    im = Image.new("RGB", (2400, 1400), (200, 210, 230))
    ImageDraw.Draw(im).ellipse([600, 300, 1800, 1100], fill=(90, 120, 80))
    im.save(src)
    return src


def test_big_flat_user_image_stays_png(tmp_path):
    # the user's own screenshots/diagrams must stay lossless, however large
    info = images.prep(_flat_big(tmp_path), tmp_path / "assets")
    assert info["kind_guess"] == "screenshot" and info["file"].endswith(".png")


def test_big_flat_downloaded_image_becomes_jpeg(tmp_path):
    # a smooth downloaded photo (few colors at 128px) used to be saved as a multi-MB PNG
    info = images.prep(_flat_big(tmp_path), tmp_path / "assets", downloaded=True)
    assert info["kind_guess"] == "screenshot" and info["file"].endswith(".jpg")


def test_small_flat_downloaded_image_stays_png(tmp_path):
    src = tmp_path / "small.png"
    Image.new("RGB", (800, 500), "white").save(src)
    assert images.prep(src, tmp_path / "assets", downloaded=True)["file"].endswith(".png")


def test_big_downloaded_image_with_alpha_stays_png(tmp_path):
    src = tmp_path / "alpha.png"
    Image.new("RGBA", (2400, 1400), (10, 20, 30, 128)).save(src)
    assert images.prep(src, tmp_path / "assets", downloaded=True)["file"].endswith(".png")


def test_small_few_color_image_stays_png(tmp_path):
    src = tmp_path / "diagram.png"
    Image.new("RGB", (1000, 1000), "white").save(src)  # exactly 1 MP: under the threshold
    assert images.prep(src, tmp_path / "assets", downloaded=True)["file"].endswith(".png")


def test_fully_opaque_rgba_photo_becomes_jpeg(tmp_path):
    src = tmp_path / "opaque.png"
    im = Image.frombytes("RGBA", (1300, 400), os.urandom(1300 * 400 * 4))
    im.putalpha(255)
    im.save(src)
    for downloaded in (True, False):
        info = images.prep(src, tmp_path / f"assets{downloaded}", downloaded=downloaded)
        assert info["file"].endswith(".jpg") and info["kind_guess"] == "photo"


def test_rgba_with_real_transparency_stays_png(tmp_path):
    src = tmp_path / "cutout.png"
    im = Image.frombytes("RGBA", (1300, 400), os.urandom(1300 * 400 * 4))
    im.putalpha(Image.new("L", im.size, 255))
    im.putpixel((0, 0), (1, 2, 3, 0))  # one transparent pixel is enough
    im.save(src)
    assert images.prep(src, tmp_path / "assets", downloaded=True)["file"].endswith(".png")


def test_opaque_la_becomes_l_before_alpha_check(tmp_path):
    src = tmp_path / "la.png"
    size = (1800, 1200)  # grayscale has at most 256 colors (looks "flat"); the download size rule makes it JPEG
    Image.merge("LA", (Image.frombytes("L", size, os.urandom(size[0] * size[1])), Image.new("L", size, 255))).save(src)
    assert images.prep(src, tmp_path / "assets", downloaded=True)["file"].endswith(".jpg")
    Image.merge("LA", (Image.frombytes("L", size, os.urandom(size[0] * size[1])), Image.new("L", size, 254))).save(src)
    assert images.prep(src, tmp_path / "assets2", downloaded=True)["file"].endswith(".png")  # not fully opaque: keeps alpha


def test_downloaded_image_over_100_megapixels_is_refused_before_decoding(tmp_path):
    src = tmp_path / "huge.png"
    Image.new("1", (10001, 10001)).save(src)  # 100.02 MP, tiny on disk
    with pytest.raises(ValueError, match="100 MP limit"):
        images.prep(src, tmp_path / "assets", downloaded=True)
    assert not (tmp_path / "assets").exists() or not list((tmp_path / "assets").iterdir())
