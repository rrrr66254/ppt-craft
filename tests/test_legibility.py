import pytest
from PIL import Image
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
    px = [(150, 150, 150)] * 4
    assert L.plan(px, INK, BG, 30)["alpha"] <= L.plan(px, INK, BG, 18)["alpha"]

def test_panel_when_low_contrast_palette():
    p = L.plan([(128, 128, 128)] * 4, "#777777", "#888888", 18)
    assert p["panel"] is True and p["alpha"] is None

def test_region_pixels_and_mapping():
    img = Image.new("RGB", (400, 200), (255, 255, 255))
    img.paste((0, 0, 0), (0, 0, 200, 200))
    box = L.slide_box_to_image_px((0, 0, 1, 1), (0, 0, 2, 1), (400, 200), (0, 0, 0, 0))
    assert box == pytest.approx((0, 0, 200, 200))
    assert set(L.region_pixels(img, box)) == {(0, 0, 0)}

def test_mapping_with_crop():
    box = L.slide_box_to_image_px((1, 0, 1, 1), (0, 0, 2, 1), (400, 200), (0.25, 0, 0.25, 0))
    assert box == pytest.approx((200, 0, 300, 200))
