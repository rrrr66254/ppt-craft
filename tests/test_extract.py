import extract_pptx_style as ex
from deckkit import Deck
from helpers import STYLE


def test_roundtrip_from_deckkit(tmp_path):
    d = Deck(STYLE)
    s = d.slide("제목")
    d.text(s, d.body_box(0, 6), "본문", color="accent")
    res = ex.extract(d.save(tmp_path / "t.pptx"))
    assert res["slide_size_in"] == [13.333, 7.5]
    assert res["theme_colors"]["accent1"] == "#1D4E89"
    assert res["theme_fonts"]["majorFont"]["latin"] == "Malgun Gothic"
    assert res["used_fonts"][0][0] == "Malgun Gothic"
    assert "#1D4E89" in dict(res["used_colors"])
    assert res["margin_guess_in"] == 0.6
