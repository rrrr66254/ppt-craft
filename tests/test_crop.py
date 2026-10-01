import pytest

from deckkit.crop import contain_box, cover_crop, effective_dpi


def test_landscape_into_square_centered():
    assert cover_crop(400, 200, 1, 1) == pytest.approx((0.25, 0, 0.25, 0))


def test_focus_at_edge_clamps_to_image():
    l, t, r, b = cover_crop(400, 200, 1, 1, focus=(0.9, 0.4, 1.0, 0.6))
    assert l == pytest.approx(0.5) and r == pytest.approx(0)


def test_portrait_slot_keeps_focus_center():
    # window width 250px, focus center 350px -> x0 = 225
    l, t, r, b = cover_crop(1000, 500, 1, 2, focus=(0.3, 0.0, 0.4, 1.0))
    assert l == pytest.approx(0.225) and r == pytest.approx(0.525)


def test_thirds_anchor_places_focus_on_third():
    # window 500px, focus x=200 (left half) -> x0 = 200 - 500/3
    l, _, _, _ = cover_crop(1000, 500, 1, 1, focus=(0.2, 0.4, 0.2, 0.6), anchor="thirds")
    assert l == pytest.approx((200 - 500 / 3) / 1000, abs=1e-5)


def test_must_keep_shifts_window():
    l, _, r, _ = cover_crop(1000, 500, 1, 1, focus=(0.0, 0.4, 0.1, 0.6), must_keep=(0.3, 0.2, 0.7, 0.8))
    assert l <= 0.3 + 1e-9 and 1 - r >= 0.7 - 1e-9


def test_must_keep_too_wide_returns_none():
    assert cover_crop(1000, 500, 1, 1, must_keep=(0.1, 0.2, 0.9, 0.8)) is None


def test_contain_box_centers():
    assert contain_box(400, 200, (0, 0, 2, 2)) == pytest.approx((0, 0.5, 2, 1))


def test_effective_dpi():
    assert effective_dpi(3000, (0.25, 0, 0.25, 0), 5) == pytest.approx(300)


def test_thirds_without_focus_equals_center():
    assert cover_crop(400, 200, 1, 1, anchor="thirds") == pytest.approx(cover_crop(400, 200, 1, 1))
