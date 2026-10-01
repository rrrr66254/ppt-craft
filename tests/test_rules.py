import json
import re

from helpers import ROOT


def test_tells_has_all_rule_families():
    text = (ROOT / "rules" / "tells.md").read_text(encoding="utf-8")
    for rid in ["L1", "L16", "C1", "C11", "T1", "T15", "I1", "I9", "W1", "W14", "K1", "K15", "S1", "S10",
                "D1", "D8", "H1", "H8", "BULLET"]:
        assert f"| {rid} |" in text, rid


def test_tells_has_imagery_rules():
    text = (ROOT / "rules" / "tells.md").read_text(encoding="utf-8")
    ids = ["I10", "I11", "I12", "I13", "C12", "C13", "C14", "C15", "D9", "T16", "W15", "W16"]
    ids += [f"L{n}" for n in range(17, 25)]
    for rid in ids:
        assert f"| {rid} |" in text, rid
    assert "Imagery" in text


def test_banned_words_compile():
    words = json.loads((ROOT / "rules" / "banned-words.json").read_text(encoding="utf-8"))
    for pats in words["per_hit"].values():
        for p in pats:
            re.compile(p)
    for spec in words["per_deck"].values():
        assert spec["min"] >= 2
        for p in spec["patterns"]:
            re.compile(p)
