import json

import pytest
from PIL import Image

import images
import render
import sample_deck
from helpers import STYLE


def test_render_missing_file_exits_1_and_keeps_old_pngs(tmp_path, capsys):
    out = tmp_path / "renders"
    out.mkdir()
    (out / "slide-01.png").write_bytes(b"old")
    with pytest.raises(SystemExit) as e:
        render.main([str(tmp_path / "nope.pptx"), "--out", str(out)])
    assert e.value.code == 1
    assert "[render] error" in capsys.readouterr().err
    assert (out / "slide-01.png").read_bytes() == b"old"


def _style(tmp_path):
    p = tmp_path / "style.json"
    p.write_text(json.dumps(STYLE), encoding="utf-8")
    return str(p)


def test_sample_bad_json_exits_1(tmp_path, capsys):
    bad = tmp_path / "sample.json"
    bad.write_text("{not json", encoding="utf-8")
    assert sample_deck.main([_style(tmp_path), str(bad), str(tmp_path / "o.pptx")]) == 1
    assert "[sample]" in capsys.readouterr().err


def test_sample_missing_image_exits_1(tmp_path, capsys):
    sample = {"title": "캐시 회고", "claim": "캐시를 붙이자 지연이 줄었다", "points": ["p99 820ms에서 410ms로"],
              "chart": {"title": "비용이 늘었다", "categories": ["7월", "8월"], "series": {"비용": [1, 2]}},
              "image": "missing.png"}
    p = tmp_path / "sample.json"
    p.write_text(json.dumps(sample, ensure_ascii=False), encoding="utf-8")
    style = {**STYLE, "cover": "image"}
    (tmp_path / "s.json").write_text(json.dumps(style), encoding="utf-8")
    assert sample_deck.main([str(tmp_path / "s.json"), str(p), str(tmp_path / "o.pptx")]) == 1
    assert "[sample]" in capsys.readouterr().err


def test_images_one_bad_file_does_not_block_others(tmp_path, capsys):
    good = tmp_path / "good.png"
    Image.new("RGB", (40, 30), "white").save(good)
    bad = tmp_path / "bad.png"
    bad.write_text("not an image", encoding="utf-8")
    out = tmp_path / "assets"
    assert images.main([str(bad), str(good), "--out", str(out)]) == 1
    assert "[images] skipped" in capsys.readouterr().err
    index = json.loads((out / "images.json").read_text(encoding="utf-8"))
    assert len(index) == 1 and next(iter(index)).startswith("good.")
