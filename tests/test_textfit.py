import sys

import pytest

from deckkit.fonts import find_font_file
from deckkit.textfit import Measurer, fit_size, has_broken_word, wrap


def test_estimate_widths():
    m = Measurer(None, 10)
    assert m.width("가나") == pytest.approx(20)
    assert m.width("ab") == pytest.approx(11)


def test_tracking_narrows():
    assert Measurer(None, 10, -0.05).width("가나") == pytest.approx(19)


def test_wrap_by_word_korean():
    m = Measurer(None, 10)
    assert wrap("가나다 라마바 사아", m, 65) == ["가나다 라마바", "사아"]


def test_long_word_breaks_by_char():
    m = Measurer(None, 10)
    assert wrap("가나다라마바사", m, 35) == ["가나다", "라마바", "사"]


def test_fit_shrinks_until_fits():
    size, ok = fit_size(["가" * 40], None, 20, 10, box_w_in=2, box_h_in=1, spacing=1.2, tracking_em=0)
    assert ok and 10 <= size < 20


def test_fit_reports_failure_at_min():
    size, ok = fit_size(["가" * 400], None, 20, 14, 2, 1, 1.2, 0)
    assert not ok and size == 14


def test_broken_word_detected():
    assert has_broken_word(["데이터베이스마이그레이션"], None, 18, 1.0, 0)
    assert not has_broken_word(["짧은 단어"], None, 18, 3.0, 0)


def test_wrap_ignores_extra_whitespace():
    assert wrap("가나다 ", Measurer(None, 10), 54) == ["가나다"]
    assert wrap("", Measurer(None, 10), 54) == [""]


@pytest.mark.skipif(sys.platform != "win32", reason="Malgun Gothic is a Windows default font")
def test_real_font_measure_and_fit():
    ref = find_font_file("Malgun Gothic")
    assert Measurer(ref, 18).width("가나다") == pytest.approx(54, abs=3)
    assert fit_size(["가나다 라마바"], ref, 18, 10, 3, 1, 1.2, 0)[1] is True


def test_long_word_wrap_fast_and_fits():
    ref = find_font_file("Malgun Gothic") or find_font_file("Arial")
    if ref is None:
        pytest.skip("no font")
    m = Measurer(ref, 18)
    lines = wrap("a" * 2000, m, 100)
    assert "".join(lines) == "a" * 2000
    assert all(m.width(ln) <= 100 or len(ln) == 1 for ln in lines)


def test_line_height_is_font_independent():
    assert Measurer(None, 10).line_height(1.5) == pytest.approx(18)
    ref = find_font_file("Malgun Gothic") or find_font_file("Arial")
    if ref is not None:
        assert Measurer(ref, 10).line_height(1.5) == pytest.approx(18)


@pytest.mark.skipif(sys.platform != "win32", reason="Malgun Gothic is a Windows default font")
def test_real_font_fit_shrinks_title_in_narrow_box():
    ref = find_font_file("Malgun Gothic", True)
    title = "캐시 도입 후 응답 시간이 40% 줄었다"
    size, ok = fit_size([title], ref, 28, 20, 4.0, 1.1, 1.35, -0.03)
    assert ok and size < 28


def test_fit_applies_safety_to_width():
    # 7 x "가" = 140pt: fits on one line in a 144pt width (100%) but overflows at 95% (136.8pt), so it must shrink
    size, ok = fit_size(["가" * 7], None, 20, 10, box_w_in=2, box_h_in=0.45, spacing=1.0, tracking_em=0)
    assert ok and size < 20


def test_broken_word_uses_safety_margin():
    assert has_broken_word(["가" * 7], None, 20, 2.0, 0)  # 140pt > 144 x 0.95


def test_vertical_tab_counts_as_a_line_without_paragraph_gap():
    m = Measurer(None, 10)
    assert wrap("가나\v다라", m, 1000) == ["가나", "다라"]
    from deckkit.textfit import text_height
    assert text_height(["가나\v다라"], m, 1000, 1.0, 5) == text_height(["가나", "다라"], m, 1000, 1.0, 0)
