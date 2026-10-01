"""Imagery lint rules (Plan 4): C12, C13, L19, L23, L24, W15, W16 and L2 by pattern tag."""
import json

import pytest
from PIL import Image

import lint
from deckkit import Deck
from helpers import STYLE


@pytest.fixture
def photo(tmp_path):
    p = tmp_path / "photo.jpg"
    img = Image.new("RGB", (2400, 1350), (40, 40, 40))
    img.paste((200, 200, 200), (1600, 0, 2400, 1350))
    img.save(p)
    return p


def _rules(path, style=None):
    return lint.lint(path, style)["findings"]


def _hits(findings, rule):
    return [f for f in findings if f["rule"] == rule]


def _style_file(tmp_path, **imagery):
    p = tmp_path / "style.json"
    p.write_text(json.dumps({**STYLE, "imagery": {**imagery}} if imagery else STYLE), encoding="utf-8")
    return p


# ---- C12: pure #000 text ----
def test_c12_pure_black_text(tmp_path):
    d = Deck(STYLE)
    s = d.slide("검은 글자는 화면에서 너무 세다")
    d.text(s, d.body_box(0, 7), "본문", color="#000000")
    hits = _hits(_rules(d.save(tmp_path / "bad.pptx")), "C12")
    assert hits and hits[0]["severity"] == "major" and hits[0]["slide"] == 1


def test_c12_dark_ink_is_fine(tmp_path):
    d = Deck(STYLE)
    s = d.slide("짙은 잉크색은 괜찮다")
    d.text(s, d.body_box(0, 7), "본문")
    assert not _hits(_rules(d.save(tmp_path / "ok.pptx")), "C12")


# ---- L24: full-bleed slides over max_bleed ----
def _bleeds(tmp_path, photo, n):
    d = Deck(STYLE)
    for i in range(n):
        d.pattern("bleed-panel", f"전면 사진 {i}", photo)
    return d.save(tmp_path / f"bleed{n}.pptx")


def test_l24_over_default_max_bleed(tmp_path, photo):
    hits = _hits(_rules(_bleeds(tmp_path, photo, 4)), "L24")
    assert len(hits) == 1 and hits[0]["severity"] == "major" and hits[0]["slide"] is None


def test_l24_at_limit_and_style_limit(tmp_path, photo):
    assert not _hits(_rules(_bleeds(tmp_path, photo, 3)), "L24")
    path = _bleeds(tmp_path, photo, 4)
    assert not _hits(_rules(path, _style_file(tmp_path, max_bleed=4)), "L24")
    assert _hits(_rules(path, _style_file(tmp_path, max_bleed=1)), "L24")


# ---- C13: texture on more than one slide ----
def _textures(tmp_path, n):
    tex = tmp_path / "tex.png"
    Image.new("RGBA", (1920, 1080), (17, 17, 17, 12)).save(tex)
    d = Deck(STYLE)
    for i in range(n):
        s = d.slide(f"질감 {i}")
        d.background(s, tex, pattern="texture")
    return d.save(tmp_path / f"tex{n}.pptx")


def test_c13_texture_on_two_slides(tmp_path):
    hits = _hits(_rules(_textures(tmp_path, 2)), "C13")
    assert len(hits) == 1 and hits[0]["severity"] == "minor"


def test_c13_single_texture_is_fine(tmp_path):
    assert not _hits(_rules(_textures(tmp_path, 1)), "C13")


# ---- L19: too many elements or a long title on an image slide ----
def test_l19_too_many_elements(tmp_path, photo):
    d = Deck(STYLE)
    s, box = d.pattern("split", "사진 옆에 글이 너무 많다", photo)
    x, y, w, _ = box
    for k in range(4):
        d.text(s, (x, y + k * 1.0, w, 0.8), f"항목 {k}")
    hits = _hits(_rules(d.save(tmp_path / "busy.pptx")), "L19")
    assert hits and hits[0]["slide"] == 1


def test_l19_three_line_title(tmp_path, photo):
    d = Deck(STYLE)
    d.pattern("split", "첫 줄\n둘째 줄\n셋째 줄", photo)
    assert _hits(_rules(d.save(tmp_path / "title.pptx")), "L19")


def test_l19_ignores_images_captions_footer_and_non_image_slides(tmp_path, photo):
    d = Deck(STYLE)
    s, box = d.pattern("inset", "사진 한 장과 짧은 설명", photo, caption="사진: 서울, 2026년 9월", span=8)
    d.text(s, box, "설명 한 줄")
    d.footer(s, "사내 세미나", 1)
    s2, _ = d.pattern("gallery", "네 곳의 현장", [photo] * 4, captions=["가", "나", "다", "라"])
    s3 = d.slide("이미지 없는 장은 세지 않는다")
    for k in range(5):
        d.text(s3, (1, 1.8 + k * 0.9, 6, 0.8), f"항목 {k}")
    assert not _hits(_rules(d.save(tmp_path / "ok.pptx")), "L19")


# ---- L23: more than 5 bullets in one frame ----
def test_l23_six_bullets(tmp_path):
    d = Deck(STYLE)
    s = d.slide("불릿이 너무 많다")
    d.text(s, d.body_box(0, 8), [f"항목 {k}" for k in range(6)], bullets=True)
    assert _hits(_rules(d.save(tmp_path / "b6.pptx")), "L23")


def test_l23_five_bullets_is_fine(tmp_path):
    d = Deck(STYLE)
    s = d.slide("불릿 다섯 개")
    d.text(s, d.body_box(0, 8), [f"항목 {k}" for k in range(5)], bullets=True)
    assert not _hits(_rules(d.save(tmp_path / "b5.pptx")), "L23")


# ---- W15: straight quotes, double hyphen, three dots in an English deck ----
@pytest.mark.parametrize("text", ['They called it "fast"', "Latency dropped--a lot", "And then..."])
def test_w15_ascii_punctuation_in_english(tmp_path, text):
    d = Deck(STYLE, lang="en")
    s = d.slide("Latency halved after the cache")
    d.text(s, d.body_box(0, 7), text)
    assert _hits(_rules(d.save(tmp_path / "w15.pptx")), "W15")


@pytest.mark.parametrize("title,text", [
    ("Latency halved after the cache", "Run lint.py --style style.json first"),
    ("Latency halved after the cache", "They called it “fast” and then…"),
    ("캐시 이후 지연이 절반", 'API 이름은 "orders"다'),
])
def test_w15_clean(tmp_path, title, text):
    d = Deck(STYLE, lang="en")
    s = d.slide(title)
    d.text(s, d.body_box(0, 7), text)
    assert not _hits(_rules(d.save(tmp_path / "ok.pptx")), "W15")


# ---- W16: fake names ----
@pytest.mark.parametrize("text", ["Owner: John Doe", "acme dashboard", "Lorem dolor", "Foo Corp revenue"])
def test_w16_fake_names(tmp_path, text):
    d = Deck(STYLE, lang="en")
    s = d.slide("Who owns the dashboard")
    d.text(s, d.body_box(0, 7), text)
    assert _hits(_rules(d.save(tmp_path / "w16.pptx")), "W16")


def test_w16_real_names(tmp_path):
    d = Deck(STYLE, lang="en")
    s = d.slide("Who owns the dashboard")
    d.text(s, d.body_box(0, 7), "Owner: Johnny Doerr at Acmetrix")
    assert not _hits(_rules(d.save(tmp_path / "ok.pptx")), "W16")


# ---- L2 by pattern tag ----
def test_l2_same_pattern_three_in_a_row(tmp_path, photo):
    d = Deck(STYLE)
    for k, side in enumerate(("left", "right", "left")):  # different geometry, same pattern
        s, box = d.pattern("split", f"사진 {k}", photo, side=side, ratio=(5, 7) if k < 2 else (6, 6))
        d.text(s, box, "본문")
    hits = _hits(_rules(d.save(tmp_path / "rep.pptx")), "L2")
    assert len(hits) == 1 and hits[0]["slide"] == 3 and "split" in hits[0]["message"]


def test_l2_varied_patterns_are_fine(tmp_path, photo):
    d = Deck(STYLE)
    d.pattern("split", "사진 1", photo, side="left")
    d.pattern("split", "사진 2", photo, side="right")
    d.pattern("inset", "사진 3", photo, caption="사진: 서울, 2026년 9월")
    assert not _hits(_rules(d.save(tmp_path / "ok.pptx")), "L2")


# ---- realistic clean deck ----
def test_clean_image_deck(tmp_path, photo):
    d = Deck(STYLE)
    s, _ = d.pattern("bleed-scrim", "현장에서 본 병목", photo, focus=(0.7, 0.0, 0.3, 1.0))
    d.footer(s, "사내 세미나 2026", 1)
    s2, box = d.pattern("split", "대기열이 입구에서 막혔다", photo, side="right")
    d.text(s2, box, ["오전 9시에 입구 대기가 가장 길었다", "출구 쪽은 비어 있었다"], bullets=True)
    d.footer(s2, "사내 세미나 2026", 2)
    s3, box = d.pattern("inset", "입구 배치를 바꾼 뒤", photo, caption="사진: 직접 촬영, 서울, 2026년 9월")
    d.text(s3, box, "대기 시간이 줄었다")
    d.text(s3, (d.m, d.H - d.m - 0.8, 6, 0.3), "Photo: 직접 촬영", "caption", color="muted")
    d.footer(s3, "사내 세미나 2026", 3)
    findings = _rules(d.save(tmp_path / "clean.pptx"), _style_file(tmp_path))
    assert not [f for f in findings if f["severity"] in ("blocker", "major")], findings
    new = {"C12", "C13", "L19", "L23", "L24", "W15", "W16", "L2"}
    assert not [f for f in findings if f["rule"] in new], findings
