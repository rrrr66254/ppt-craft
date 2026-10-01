import pytest
from PIL import Image, ImageDraw
from deckkit import legibility as L

INK, BG = "#111111", "#FFFFFF"

def test_contrast_black_white():
    assert L.contrast((0, 0, 0), (255, 255, 255)) == pytest.approx(21.0, abs=0.01)

def test_dark_photo_light_text_no_scrim():
    px = [(20, 20, 20)] * 10
    p = L.plan(px, INK, BG, 18)
    assert p == {"text": "bg", "alpha": 0.0, "panel": False, "ratio": p["ratio"]} and p["ratio"] >= 4.5

def test_light_photo_dark_text_no_scrim():
    p = L.plan([(240, 240, 240)] * 10, INK, BG, 18)
    assert p["text"] == "ink" and p["alpha"] == 0.0

def test_mid_gray_needs_scrim():
    p = L.plan([(121, 121, 121)] * 10, INK, BG, 18)
    assert not p["panel"] and 0 < p["alpha"] <= 0.7 and p["ratio"] >= 4.5

def test_worst_case_pixel_drives_decision():
    mixed = [(10, 10, 10)] * 9 + [(250, 250, 250)]
    p = L.plan(mixed, INK, BG, 18)
    assert p["ratio"] >= 4.5  # the bright speck must also pass

def test_large_text_lower_threshold():
    px = [(121, 121, 121)] * 4  # needs a scrim at 18 pt but passes bare at 30 pt
    assert L.plan(px, INK, BG, 18)["alpha"] > 0
    assert L.plan(px, INK, BG, 30)["alpha"] == 0

def test_panel_when_low_contrast_palette():
    p = L.plan([(128, 128, 128)] * 4, "#777777", "#888888", 18)
    assert p["panel"] is True and p["alpha"] is None
    assert p["ratio"] == pytest.approx(L.contrast(L.hex_rgb("#777777"), L.hex_rgb("#888888")), abs=0.01)
    assert p["palette_ok"] is False


def test_panel_with_good_palette_is_ok():
    p = L.plan([(10, 10, 10), (250, 250, 250)], "#666666", "#FFFFFF", 18)
    assert p["panel"] is True and p["palette_ok"] is True and p["ratio"] > 4.5

def test_region_pixels_and_mapping():
    img = Image.new("RGB", (400, 200), (255, 255, 255))
    img.paste((0, 0, 0), (0, 0, 200, 200))
    box = L.slide_box_to_image_px((0, 0, 1, 1), (0, 0, 2, 1), (400, 200), (0, 0, 0, 0))
    assert box == pytest.approx((0, 0, 200, 200))
    assert set(L.region_pixels(img, box)) == {(0, 0, 0)}

def test_mapping_with_crop():
    box = L.slide_box_to_image_px((1, 0, 1, 1), (0, 0, 2, 1), (400, 200), (0.25, 0, 0.25, 0))
    assert box == pytest.approx((200, 0, 300, 200))


def test_mapping_with_vertical_crop():
    box = L.slide_box_to_image_px((0, 0.5, 1, 0.5), (0, 0, 2, 1), (200, 400), (0, 0.25, 0, 0.25))
    assert box == pytest.approx((0, 200, 100, 300))


def test_thin_bright_horizon_is_not_averaged_away():
    img = Image.new("RGB", (4000, 200), (10, 10, 10))
    ImageDraw.Draw(img).rectangle((0, 80, 3999, 109), fill=(255, 255, 255))  # 30 px bright horizon
    px = L.region_pixels(img, (0, 0, 4000, 200))
    assert max(px)[0] >= 250 and min(px)[0] <= 12
    p = L.plan(px, INK, BG, 18)
    assert p["panel"] or p["alpha"] > 0  # light text bare would fail on the stripe
    if not p["panel"]:
        txt, scr = (L.hex_rgb(BG), L.hex_rgb(INK)) if p["text"] == "bg" else (L.hex_rgb(INK), L.hex_rgb(BG))
        for pix in ((255, 255, 255), (10, 10, 10)):
            assert L.contrast(txt, L._blend(pix, scr, p["alpha"])) >= 4.5


def test_region_pixels_clamps_box_past_edges():
    img = Image.new("RGB", (400, 200), (30, 30, 30))
    assert set(L.region_pixels(img, (350, 150, 900, 900))) == {(30, 30, 30)}  # right/bottom past the edge
    assert set(L.region_pixels(img, (-50, -50, 20, 20))) == {(30, 30, 30)}
    assert L.region_pixels(img, (399.6, 0, 400, 10))  # sliver at the edge still yields pixels


@pytest.mark.parametrize("box", [(500, 0, 600, 100), (400, 0, 450, 100), (-100, -100, -10, -10), (0, 200, 10, 300)])
def test_region_pixels_outside_image_raises(box):
    with pytest.raises(ValueError, match="text box is outside the image"):
        L.region_pixels(Image.new("RGB", (400, 200)), box)


def test_plan_empty_raises():
    with pytest.raises(ValueError, match="no pixels"):
        L.plan([], INK, BG, 18)


def test_alpha_steps_are_exact_decimals():
    p = L.plan([(121, 121, 121)] * 4, INK, BG, 18)
    assert p["alpha"] == 0.05
    p = L.plan([(100, 100, 100), (140, 140, 140)] * 2, INK, BG, 18)
    assert round(p["alpha"] * 100) % 5 == 0 and p["alpha"] == round(p["alpha"], 2)
