import io
import json
import os
import urllib.parse
from pathlib import Path

import pytest
from PIL import Image

import assets
import netutil

FIX = Path(__file__).parent / "fixtures" / "net"
MIN_W = assets.SOURCES["min_photo_width"]


def fixture(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


# ---------- Task 2: adapters ----------

def test_strip_html():
    assert assets.strip_html('<a href="x">Esquilo</a> &amp; co') == "Esquilo & co"
    assert assets.strip_html("  a \n  b ") == "a b"


def test_openverse_request_has_no_category_and_uses_source_list():
    url, headers = assets.REQUESTS["openverse"]("red squirrel", 12, None)
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    assert url.startswith("https://api.openverse.org/v1/images/?")
    assert q["q"] == ["red squirrel"] and q["page_size"] == ["12"]
    assert q["license_type"] == ["commercial,modification"]
    assert q["source"] == ["nasa,met,rijksmuseum,nappy"]
    assert "category" not in q and not headers


def test_openverse_parse():
    got = assets.PARSERS["openverse"](fixture("openverse"), MIN_W)
    # openverse widths are unreliable (null for Met, capped at 1024 for NASA): no width filter at search time
    assert [c["id"] for c in got] == ["openverse:b1c1f097-1166-4f38-aa7f-e3088bb37b7a",
                                      "openverse:0d9b7f0e-4b0e-4d60-9a0e-0a3f4d2a7c11"]
    assert got[1]["width"] == 600 and got[1]["license"] == "CC0 1.0"
    assert got[0] == {
        "id": "openverse:b1c1f097-1166-4f38-aa7f-e3088bb37b7a", "source": "openverse",
        "title": "Squirrel posing",
        "thumb_url": "https://api.openverse.org/v1/images/b1c1f097-1166-4f38-aa7f-e3088bb37b7a/thumb/",
        "full_url": "https://upload.wikimedia.org/wikipedia/commons/1/1c/Squirrel_posing.jpg",
        "width": 1706, "height": 1426, "author": "Peter Trimming", "author_url": None,
        "landing_url": "https://commons.wikimedia.org/w/index.php?curid=29980115",
        "license": "CC BY 2.0", "license_url": "https://creativecommons.org/licenses/by/2.0/",
        "attribution_required": True, "ai_risk": True}


def test_openverse_license_names_and_attribution():
    data = fixture("openverse")
    for lic, ver, name, required in (("cc0", "1.0", "CC0 1.0", False),
                                     ("pdm", "1.0", "Public Domain Mark 1.0", False),
                                     ("by-sa", "4.0", "CC BY-SA 4.0", True)):
        r = dict(data["results"][1], license=lic, license_version=ver, width=2000, creator=None)
        c = assets.PARSERS["openverse"]({"results": [r]}, MIN_W)[0]
        assert (c["license"], c["attribution_required"], c["author"]) == (name, required, "unknown")


def test_openverse_drops_unsupported_filetype_and_missing_url():
    base = dict(fixture("openverse")["results"][0])
    got = assets.PARSERS["openverse"]({"results": [dict(base, filetype="svg"), dict(base, url=None)]}, MIN_W)
    assert got == []


def test_wikimedia_request():
    url, headers = assets.REQUESTS["wikimedia"]("red squirrel", 12, None)
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    assert url.startswith("https://commons.wikimedia.org/w/api.php?")
    assert q["gsrsearch"] == ['red squirrel -deepcategory:"AI-generated images"']
    assert q["gsrlimit"] == ["12"] and q["iiurlwidth"] == ["640"] and q["gsrnamespace"] == ["6"]
    assert q["generator"] == ["search"] and q["prop"] == ["imageinfo"]
    assert q["iiprop"] == ["url|extmetadata|size|mime"] and not headers


def test_wikimedia_parse():
    got = assets.PARSERS["wikimedia"](fixture("wikimedia"), MIN_W)
    assert len(got) == 1  # the svg is dropped
    assert got[0] == {
        "id": "wikimedia:47900137", "source": "wikimedia",
        "title": "Grey squirrel (Sciurus carolinensis) 02",
        "thumb_url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/0/07/Grey_squirrel_%28Sciurus_carolinensis%29_02.jpg/640px-Grey_squirrel_%28Sciurus_carolinensis%29_02.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail",
        "full_url": "https://upload.wikimedia.org/wikipedia/commons/0/07/Grey_squirrel_%28Sciurus_carolinensis%29_02.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original",
        "width": 3459, "height": 2307, "author": "Charles J. Sharp", "author_url": None,
        "landing_url": "https://commons.wikimedia.org/wiki/File:Grey_squirrel_(Sciurus_carolinensis)_02.jpg",
        "license": "CC BY-SA 4.0", "license_url": "https://creativecommons.org/licenses/by-sa/4.0",
        "attribution_required": True, "ai_risk": False}


def test_wikimedia_no_query_results_is_empty():
    assert assets.PARSERS["wikimedia"]({"batchcomplete": ""}, MIN_W) == []


def test_pexels_request_and_parse():
    url, headers = assets.REQUESTS["pexels"]("red squirrel", 12, "KEY1")
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    assert url.startswith("https://api.pexels.com/v1/search?")
    assert q["query"] == ["red squirrel"] and q["per_page"] == ["12"]
    assert headers == {"Authorization": "KEY1"}
    got = assets.PARSERS["pexels"](fixture("pexels"), MIN_W)
    assert len(got) == 1  # the 800px one is dropped
    assert got[0] == {
        "id": "pexels:2014422", "source": "pexels", "title": "Brown Rocks During Golden Hour",
        "thumb_url": "https://images.pexels.com/photos/2014422/pexels-photo-2014422.jpeg?auto=compress&cs=tinysrgb&h=350",
        "full_url": "https://images.pexels.com/photos/2014422/pexels-photo-2014422.jpeg",
        "width": 3024, "height": 2016, "author": "Joey Farina", "author_url": "https://www.pexels.com/@joey",
        "landing_url": "https://www.pexels.com/photo/brown-rocks-during-golden-hour-2014422/",
        "license": "Pexels License", "license_url": "https://www.pexels.com/license/",
        "attribution_required": False, "ai_risk": False}


def test_pixabay_request_and_parse():
    url, headers = assets.REQUESTS["pixabay"]("red squirrel", 1, "KEY2")
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    assert url.startswith("https://pixabay.com/api/?")
    assert q["key"] == ["KEY2"] and q["q"] == ["red squirrel"] and q["image_type"] == ["photo"]
    assert q["safesearch"] == ["true"] and q["per_page"] == ["3"]  # pixabay minimum is 3
    assert not headers
    got = assets.PARSERS["pixabay"](fixture("pixabay"), MIN_W)
    assert len(got) == 1  # the 1000px one is dropped
    assert got[0] == {
        "id": "pixabay:195893", "source": "pixabay", "title": "blossom",
        "thumb_url": "https://pixabay.com/get/g1234_640.jpg",
        "full_url": "https://pixabay.com/get/g5678_1280.jpg",
        "width": 1280, "height": 853, "author": "Josch13",
        "author_url": "https://pixabay.com/users/Josch13-48777/",
        "landing_url": "https://pixabay.com/photos/blossom-bloom-flower-195893/",
        "license": "Pixabay Content License", "license_url": "https://pixabay.com/service/license-summary/",
        "attribution_required": False, "ai_risk": True}


def test_pixabay_size_is_scaled_to_large_image_cap():
    hit = fixture("pixabay")["hits"][0]
    portrait = dict(hit, imageWidth=2667, imageHeight=4000)
    c = assets.PARSERS["pixabay"]({"hits": [portrait]}, 0)[0]
    assert (c["width"], c["height"]) == (853, 1280)
    assert assets.PARSERS["pixabay"]({"hits": [portrait]}, MIN_W) == []  # 853px wide < min_photo_width
    small = dict(hit, imageWidth=1250, imageHeight=900)
    assert (assets.PARSERS["pixabay"]({"hits": [small]}, 0)[0]["width"]) == 1250  # not upscaled


def test_wikimedia_title_extension_stripped_only_at_end():
    data = fixture("wikimedia")
    page = data["query"]["pages"]["47900137"]
    page["title"] = "File:Photo.png.JPG"
    assert assets.PARSERS["wikimedia"](data, MIN_W)[0]["title"] == "Photo.png"
    page["title"] = "File:Squirrel v1.2 final"
    assert assets.PARSERS["wikimedia"](data, MIN_W)[0]["title"] == "Squirrel v1.2 final"


def test_candidates_missing_full_url_are_dropped():
    data = fixture("pexels")
    data["photos"][0]["src"].pop("original")
    assert assets.PARSERS["pexels"](data, MIN_W) == []


# ---------- Task 3: CLI ----------

HOSTS = {"api.openverse.org": "openverse", "commons.wikimedia.org": "wikimedia",
         "api.pexels.com": "pexels", "pixabay.com": "pixabay"}


def png_bytes(size=(8, 8), color="red"):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def net(monkeypatch):
    """Fake netutil: get_json serves fixtures by host (or raises), get_bytes serves PNGs. Records every call."""
    noise = Image.frombytes("RGB", (1300, 400), os.urandom(1300 * 400 * 3))  # many colors: prep() treats it as a photo
    buf = io.BytesIO()
    noise.save(buf, "PNG")
    state = {"json": [], "bytes": [], "errors": {}, "empty": set(), "full": buf.getvalue()}
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)

    def fake_json(url, *, headers=None, cache_dir=None, ttl=86400):
        src = HOSTS[urllib.parse.urlsplit(url).netloc]
        state["json"].append((src, url, headers, cache_dir))
        if "pageids=" in url:  # `photo get` asking Wikimedia for a 3000px rendition
            if "pageinfo_error" in state:
                raise state["pageinfo_error"]
            data = fixture("wikimedia")
            for page in data["query"]["pages"].values():
                info = page["imageinfo"][0]
                if state.get("pageinfo_no_thumb"):
                    info.pop("thumburl", None)
                else:
                    info["thumburl"] = "https://thumb.wikimedia.org/3000px-rendition.jpg"
            return data
        if src in state["errors"]:
            raise state["errors"][src]
        if src in state.get("override", {}):
            return state["override"][src]
        if src in state["empty"]:
            return {}
        return fixture(src)

    def fake_bytes(url, *, headers=None, timeout=60, max_bytes=50_000_000):
        state["bytes"].append((url, max_bytes))
        return state["full"] if max_bytes > 3_000_000 else png_bytes()

    monkeypatch.setattr(netutil, "get_json", fake_json)
    monkeypatch.setattr(netutil, "get_bytes", fake_bytes)
    return state


def search(tmp_path, *extra):
    return assets.main(["photo", "search", "red squirrel", "--out", str(tmp_path / "assets" / "_cand"),
                        "--cache", str(tmp_path / "cache"), *extra])


def cands(tmp_path):
    return json.loads((tmp_path / "assets" / "_cand" / "candidates.json").read_text(encoding="utf-8"))


def test_search_without_keys_uses_openverse_and_wikimedia(net, tmp_path, capsys):
    assert search(tmp_path) == 0
    err = capsys.readouterr()
    assert [c[0] for c in net["json"]] == ["openverse", "wikimedia"]
    assert "[assets] skip pexels: PEXELS_API_KEY not set" in err.err
    assert "[assets] skip pixabay: PIXABAY_API_KEY not set" in err.err
    records = cands(tmp_path)
    assert [r["source"] for r in records] == ["openverse", "openverse", "wikimedia"]
    for r in records:
        assert (tmp_path / "assets" / "_cand" / r["thumb_file"]).exists()
    assert records[0]["thumb_file"] == "openverse_b1c1f097_1166_4f38_aa7f_e3088bb37b7a.png"
    assert all(c[3] == str(tmp_path / "cache") or c[3] == tmp_path / "cache" for c in net["json"])
    assert all(b[1] == 3_000_000 for b in net["bytes"])
    assert "openverse:b1c1f097-1166-4f38-aa7f-e3088bb37b7a  openverse  CC BY 2.0  1706x1426  ai_risk" in err.out
    assert "wikimedia:47900137  wikimedia  CC BY-SA 4.0  3459x2307" in err.out


def test_search_with_keys_walks_in_policy_order_and_stops_at_n(net, tmp_path, monkeypatch):
    monkeypatch.setenv("PEXELS_API_KEY", "PK")
    monkeypatch.setenv("PIXABAY_API_KEY", "XK")
    assert search(tmp_path, "--n", "2") == 0
    assert [c[0] for c in net["json"]] == ["pexels", "openverse"]  # 1 pexels + 1 openverse reaches n=2
    assert net["json"][0][2] == {"Authorization": "PK"}
    assert [r["source"] for r in cands(tmp_path)] == ["pexels", "openverse"]


def test_search_sources_filter_and_unknown_source(net, tmp_path, monkeypatch, capsys):
    assert search(tmp_path, "--sources", "wikimedia") == 0
    assert [c[0] for c in net["json"]] == ["wikimedia"]
    assert search(tmp_path, "--sources", "unsplash") == 2
    assert "unsplash" in capsys.readouterr().err


def test_search_rate_limited_continues(net, tmp_path, capsys):
    net["errors"]["openverse"] = netutil.RateLimited("api.openverse.org: rate limited")
    assert search(tmp_path) == 0
    assert "[assets] skip openverse: api.openverse.org: rate limited" in capsys.readouterr().err
    assert [r["source"] for r in cands(tmp_path)] == ["wikimedia"]


def test_search_net_error_continues(net, tmp_path, capsys):
    net["errors"]["wikimedia"] = netutil.NetError("x -> HTTP 500")
    assert search(tmp_path) == 0
    assert "[assets] skip wikimedia: x -> HTTP 500" in capsys.readouterr().err
    assert [r["source"] for r in cands(tmp_path)] == ["openverse", "openverse"]


def test_search_nothing_found_exits_1(net, tmp_path, capsys):
    net["empty"].update({"openverse", "wikimedia"})
    assert search(tmp_path) == 1
    assert '[assets] no photos found for "red squirrel"' in capsys.readouterr().err
    assert not (tmp_path / "assets" / "_cand" / "candidates.json").exists()


def test_search_thumbnail_failure_skips_that_candidate(net, tmp_path, monkeypatch, capsys):
    real = netutil.get_bytes

    def flaky(url, **kw):
        if "openverse" in url:
            raise netutil.NetError(f"{url} -> HTTP 404")
        return real(url, **kw)

    monkeypatch.setattr(netutil, "get_bytes", flaky)
    assert search(tmp_path) == 0
    assert "[assets] skip thumbnail openverse:" in capsys.readouterr().err
    assert [r["source"] for r in cands(tmp_path)] == ["wikimedia"]


def test_search_bad_usage_exits_2(net, tmp_path):
    with pytest.raises(SystemExit) as e:
        assets.main(["photo", "search"])  # no query
    assert e.value.code == 2
    assert search(tmp_path, "--n", "0") == 2


def test_second_search_keeps_earlier_candidates(net, tmp_path):
    search(tmp_path, "--sources", "openverse")
    search(tmp_path, "--sources", "wikimedia")
    assert [r["source"] for r in cands(tmp_path)] == ["openverse", "openverse", "wikimedia"]


def test_default_cache_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "plug"))
    assert assets.default_cache() == tmp_path / "plug" / "cache"
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA")
    assert assets.default_cache() == Path.home() / ".cache" / "ppt-craft"


def get(tmp_path, cid):
    return assets.main(["photo", "get", cid, "--cand", str(tmp_path / "assets" / "_cand"),
                        "--out", str(tmp_path / "assets")])


def test_get_saves_file_index_and_credits(net, tmp_path, capsys):
    search(tmp_path)
    capsys.readouterr()
    assert get(tmp_path, "wikimedia:47900137") == 0
    out = tmp_path / "assets"
    assert capsys.readouterr().out.strip() == "wikimedia-47900137.jpg"
    assert (out / "wikimedia-47900137.jpg").exists()
    assert net["bytes"][-1] == ("https://thumb.wikimedia.org/3000px-rendition.jpg", 50_000_000)
    assert "pageids=47900137" in net["json"][-1][1] and "iiurlwidth=3000" in net["json"][-1][1]
    index = json.loads((out / "images.json").read_text(encoding="utf-8"))
    assert index["wikimedia-47900137.jpg"]["kind_guess"] == "photo"
    assert index["wikimedia-47900137.jpg"]["focus"] is None
    credits = json.loads((out / "credits.json").read_text(encoding="utf-8"))
    assert len(credits) == 1
    rec = credits[0]
    import datetime
    assert rec == {"file": "wikimedia-47900137.jpg", "source": "wikimedia",
                   "title": "Grey squirrel (Sciurus carolinensis) 02", "author": "Charles J. Sharp",
                   "author_url": None,
                   "landing_url": "https://commons.wikimedia.org/wiki/File:Grey_squirrel_(Sciurus_carolinensis)_02.jpg",
                   "license": "CC BY-SA 4.0", "license_url": "https://creativecommons.org/licenses/by-sa/4.0",
                   "attribution_required": True, "ai_risk": False, "share_alike": True,
                   "fetched": datetime.date.today().isoformat()}


def test_get_reget_keeps_focus_and_replaces_credit(net, tmp_path):
    search(tmp_path)
    get(tmp_path, "openverse:b1c1f097-1166-4f38-aa7f-e3088bb37b7a")
    out = tmp_path / "assets"
    name = "openverse-b1c1f097-1166-4f38-aa7f-e3088bb37b7a.jpg"
    index = json.loads((out / "images.json").read_text(encoding="utf-8"))
    index[name]["focus"] = [0.1, 0.1, 0.5, 0.5]
    index[name]["type"] = "photo"
    (out / "images.json").write_text(json.dumps(index), encoding="utf-8")
    get(tmp_path, "wikimedia:47900137")
    get(tmp_path, "openverse:b1c1f097-1166-4f38-aa7f-e3088bb37b7a")
    again = json.loads((out / "images.json").read_text(encoding="utf-8"))
    assert again[name]["focus"] == [0.1, 0.1, 0.5, 0.5] and again[name]["type"] == "photo"
    assert sorted(again) == sorted([name, "wikimedia-47900137.jpg"])
    credits = json.loads((out / "credits.json").read_text(encoding="utf-8"))
    assert sorted(c["file"] for c in credits) == sorted(again)  # replaced, not duplicated
    assert next(c for c in credits if c["file"] == name)["ai_risk"] is True


def test_get_pexels_credit_not_required(net, tmp_path, monkeypatch):
    monkeypatch.setenv("PEXELS_API_KEY", "PK")
    search(tmp_path, "--sources", "pexels")
    assert get(tmp_path, "pexels:2014422") == 0
    rec = json.loads((tmp_path / "assets" / "credits.json").read_text(encoding="utf-8"))[0]
    assert rec["attribution_required"] is False and rec["license"] == "Pexels License"
    assert rec["author_url"] == "https://www.pexels.com/@joey"


def test_get_unknown_id_exits_1(net, tmp_path, capsys):
    search(tmp_path)
    capsys.readouterr()
    assert get(tmp_path, "pexels:nope") == 1
    assert "[assets] unknown candidate id: pexels:nope" in capsys.readouterr().err
    assert get(tmp_path / "other", "pexels:nope") == 1  # no candidates.json at all


def test_get_download_failure_exits_1(net, tmp_path, monkeypatch, capsys):
    search(tmp_path)
    capsys.readouterr()

    def boom(url, **kw):
        raise netutil.NetError(f"{url} -> HTTP 404")

    monkeypatch.setattr(netutil, "get_bytes", boom)
    assert get(tmp_path, "wikimedia:47900137") == 1
    assert "[assets] download failed" in capsys.readouterr().err
    assert not (tmp_path / "assets" / "credits.json").exists()


def write_credits(tmp_path, records):
    d = tmp_path / "assets"
    d.mkdir(exist_ok=True)
    (d / "credits.json").write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    return d


def test_credits_output_order_and_format(tmp_path, capsys):
    base = {"author_url": None, "landing_url": "https://x/land", "license_url": "https://x/lic", "ai_risk": False,
            "fetched": "2026-10-01"}
    d = write_credits(tmp_path, [
        dict(base, file="a.jpg", source="pexels", title="Rocks", author="Joey", license="Pexels License",
             attribution_required=False),
        dict(base, file="b.jpg", source="wikimedia", title="Squirrel", author="Charles J. Sharp",
             license="CC BY-SA 4.0", attribution_required=True, share_alike=True),
    ])
    assert assets.main(["credits", str(d), "--lang", "en"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines == ['* Photo: "Squirrel" by Charles J. Sharp, Wikimedia Commons, CC BY-SA 4.0 (SA) (https://x/lic) https://x/land',
                     '  Photo: "Rocks" by Joey, Pexels, Pexels License']
    assert assets.main(["credits", str(d), "--lang", "ko"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines == ['* 사진: "Squirrel" — Charles J. Sharp, Wikimedia Commons, CC BY-SA 4.0 (SA) (https://x/lic) https://x/land',
                     '  사진: "Rocks" — Joey, Pexels, Pexels License']


def test_credits_default_lang_is_en_and_empty_ok(tmp_path, capsys):
    assert assets.main(["credits", str(tmp_path / "nowhere")]) == 0
    cap = capsys.readouterr()
    assert cap.out == "" and "[assets] no credits" in cap.err


# ---------- review-fix tests ----------

def test_credits_no_title_omits_quotes_and_missing_fields_tolerated(tmp_path, capsys):
    d = write_credits(tmp_path, [{"file": "a.jpg", "source": "pexels", "title": "", "author": "Joey", "license": "Pexels License"},
                                 {"file": "b.jpg"}, "junk", 7])
    assert assets.main(["credits", str(d), "--lang", "en"]) == 0
    assert capsys.readouterr().out.splitlines() == ["  Photo by Joey, Pexels, Pexels License",
                                                    "  Photo by unknown, , unknown"]
    assets.main(["credits", str(d), "--lang", "ko"])
    assert capsys.readouterr().out.splitlines()[0] == "  사진: Joey, Pexels, Pexels License"


def test_credits_required_without_urls_adds_nothing(tmp_path, capsys):
    d = write_credits(tmp_path, [{"file": "a.jpg", "source": "pexels", "title": "T", "author": "A", "license": "CC BY 2.0",
                                  "attribution_required": True}])
    assets.main(["credits", str(d)])
    assert capsys.readouterr().out.splitlines() == ['* Photo: "T" by A, Pexels, CC BY 2.0']


def test_load_list_keeps_only_dicts(tmp_path):
    f = tmp_path / "x.json"
    f.write_text('[{"id": 1}, "junk", 3, null, {"id": 2}]', encoding="utf-8")
    assert assets._load_list(f) == [{"id": 1}, {"id": 2}]
    f.write_text('{"not": "a list"}', encoding="utf-8")
    assert assets._load_list(f) == []


def test_unknown_license_dropped_all_sources():
    ov = fixture("openverse")
    for r in ov["results"]:
        r["license"] = None
    assert assets.PARSERS["openverse"](ov, MIN_W) == []
    wm = fixture("wikimedia")
    wm["query"]["pages"]["47900137"]["imageinfo"][0]["extmetadata"].pop("LicenseShortName")
    assert assets.PARSERS["wikimedia"](wm, MIN_W) == []
    wm["query"]["pages"]["47900137"]["imageinfo"][0]["extmetadata"]["LicenseShortName"] = {"value": "unknown"}
    assert assets.PARSERS["wikimedia"](wm, MIN_W) == []


def test_gfdl_only_dropped_but_dual_license_kept():
    for name, kept in (("GFDL 1.2", False), ("GFDL", False), ("GFDL 1.2 or CC BY-SA 3.0", True), ("CC BY 4.0", True)):
        wm = fixture("wikimedia")
        wm["query"]["pages"]["47900137"]["imageinfo"][0]["extmetadata"]["LicenseShortName"] = {"value": name}
        assert bool(assets.PARSERS["wikimedia"](wm, MIN_W)) is kept, name


def test_wikimedia_author_falls_back_to_credit_then_unknown():
    wm = fixture("wikimedia")
    meta = wm["query"]["pages"]["47900137"]["imageinfo"][0]["extmetadata"]
    meta.pop("Artist")
    assert assets.PARSERS["wikimedia"](wm, MIN_W)[0]["author"] == "unknown"
    meta["Credit"] = {"value": '<a href="x">Own work</a> by <b>Someone</b>'}
    assert assets.PARSERS["wikimedia"](wm, MIN_W)[0]["author"] == "Own work by Someone"


def test_rate_limit_mid_thumbnails_stops_that_source(net, tmp_path, monkeypatch, capsys):
    real = netutil.get_bytes
    seen = []

    def limited(url, **kw):
        seen.append(url)
        if "openverse.org" in url:
            raise netutil.RateLimited("api.openverse.org: rate limited (Retry-After: 60)")
        return real(url, **kw)

    ov = fixture("openverse")
    ov["results"][1]["width"] = 2000  # two candidates survive the width filter, so a second thumbnail could be tried
    monkeypatch.setattr(netutil, "get_bytes", limited)
    monkeypatch.setattr(netutil, "get_json",
                        lambda url, **kw: ov if "openverse.org" in url else fixture("wikimedia"))
    assert search(tmp_path) == 0
    assert sum("openverse.org" in u for u in seen) == 1  # the host is not hit again after the 429
    assert "[assets] skip openverse: api.openverse.org: rate limited (Retry-After: 60)" in capsys.readouterr().err
    assert [r["source"] for r in cands(tmp_path)] == ["wikimedia"]


def test_thumbnail_formats_from_real_content(net, tmp_path, monkeypatch, capsys):
    def img(fmt):
        buf = io.BytesIO()
        Image.new("RGB", (8, 8), "red").save(buf, fmt)
        return buf.getvalue()

    served = {"openverse": img("GIF"), "wikimedia": img("WEBP")}
    monkeypatch.setattr(netutil, "get_bytes",
                        lambda url, **kw: served["openverse" if "openverse.org" in url else "wikimedia"])
    assert search(tmp_path) == 0
    err = capsys.readouterr().err
    assert "[assets] skip thumbnail openverse:" in err and "unsupported thumbnail format GIF" in err
    recs = cands(tmp_path)
    assert [r["source"] for r in recs] == ["wikimedia"] and recs[0]["thumb_file"].endswith(".webp")


def test_thumbnail_decode_problems_are_skipped_not_fatal(net, tmp_path, monkeypatch, capsys):
    def bomb(*a, **kw):
        raise Image.DecompressionBombError("too many pixels")

    monkeypatch.setattr(assets.Image, "open", bomb)
    assert search(tmp_path) == 1
    assert "too many pixels" in capsys.readouterr().err


def test_get_low_res_flagged_in_credits_with_warning(net, tmp_path, capsys):
    buf = io.BytesIO()
    Image.frombytes("RGB", (800, 300), os.urandom(800 * 300 * 3)).save(buf, "PNG")
    net["full"] = buf.getvalue()
    search(tmp_path)
    capsys.readouterr()
    assert get(tmp_path, "wikimedia:47900137") == 0
    cap = capsys.readouterr()
    assert "[assets] warning: wikimedia-47900137.jpg is only 800px wide (source reported 3459px)" in cap.err
    out = tmp_path / "assets"
    assert (out / "wikimedia-47900137.jpg").exists()  # kept
    assert json.loads((out / "credits.json").read_text(encoding="utf-8"))[0]["low_res"] is True


def test_get_normal_size_has_no_low_res_flag(net, tmp_path, capsys):
    search(tmp_path)
    get(tmp_path, "wikimedia:47900137")
    assert "low_res" not in json.loads((tmp_path / "assets" / "credits.json").read_text(encoding="utf-8"))[0]
    assert "warning" not in capsys.readouterr().err


def test_get_wikimedia_falls_back_to_original_url(net, tmp_path):
    search(tmp_path)
    for tweak in ({"pageinfo_error": netutil.NetError("x -> HTTP 500")}, {"pageinfo_no_thumb": True}):
        net.pop("pageinfo_error", None)
        net.pop("pageinfo_no_thumb", None)
        net.update(tweak)
        assert get(tmp_path, "wikimedia:47900137") == 0
        assert "upload.wikimedia.org" in net["bytes"][-1][0]


def test_get_non_wikimedia_downloads_full_url_directly(net, tmp_path):
    search(tmp_path, "--sources", "openverse")
    n_json = len(net["json"])
    assert get(tmp_path, "openverse:b1c1f097-1166-4f38-aa7f-e3088bb37b7a") == 0
    assert len(net["json"]) == n_json and net["bytes"][-1][0].endswith("Squirrel_posing.jpg")


def test_share_alike_flag():
    assert assets._share_alike("CC BY-SA 4.0") and assets._share_alike("CC BY-NC-SA 2.0")
    assert not assets._share_alike("CC BY 4.0") and not assets._share_alike("Pexels License")
    assert not assets._share_alike("CC0 1.0")


def test_candidates_json_written_atomically(net, tmp_path, monkeypatch):
    import images
    search(tmp_path, "--sources", "openverse")
    before = (tmp_path / "assets" / "_cand" / "candidates.json").read_text(encoding="utf-8")

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(images.os, "replace", boom)
    with pytest.raises(OSError):
        search(tmp_path, "--sources", "wikimedia")
    assert (tmp_path / "assets" / "_cand" / "candidates.json").read_text(encoding="utf-8") == before
    assert not list((tmp_path / "assets" / "_cand").glob("*.tmp"))


def test_get_wikimedia_rate_limited_lookup_exits_1_without_downloading_original(net, tmp_path, capsys):
    search(tmp_path)
    capsys.readouterr()
    net["pageinfo_error"] = netutil.RateLimited("commons.wikimedia.org: rate limited (Retry-After: 30)")
    n_bytes = len(net["bytes"])
    assert get(tmp_path, "wikimedia:47900137") == 1
    assert "[assets] download failed: commons.wikimedia.org: rate limited" in capsys.readouterr().err
    assert len(net["bytes"]) == n_bytes and not (tmp_path / "assets" / "credits.json").exists()


# ---------- openverse sizes, silent sources, credits --files ----------

def test_openverse_missing_width_height_kept_as_unknown_and_not_filtered():
    data = fixture("openverse")
    data["results"][0].update(width=None, height=None)
    data["results"][1].update(width=1024, height=683)  # NASA: capped, still kept
    got = assets.PARSERS["openverse"](data, MIN_W)
    assert [(c["width"], c["height"]) for c in got] == [(0, 0), (1024, 683)]
    assert assets._summary(got[0]).endswith("CC BY 2.0  ?x?  ai_risk")
    assert assets._summary(got[1]).endswith("CC0 1.0  1024x683  ai_risk")


def test_other_sources_keep_the_width_filter():
    assert assets.PARSERS["wikimedia"](fixture("wikimedia"), 10_000) == []
    assert assets.PARSERS["pexels"](fixture("pexels"), 10_000) == []
    assert assets.PARSERS["pixabay"](fixture("pixabay"), 10_000) == []


def test_search_summary_shows_unknown_size(net, tmp_path, capsys):
    ov = fixture("openverse")
    ov["results"][0].update(width=None, height=None)
    net["override"] = {"openverse": ov}
    assert search(tmp_path, "--sources", "openverse") == 0
    assert "openverse  CC BY 2.0  ?x?  ai_risk" in capsys.readouterr().out
    assert [r["width"] for r in cands(tmp_path)] == [0, 600]


def test_source_with_no_results_is_reported(net, tmp_path, capsys):
    net["empty"].add("openverse")
    assert search(tmp_path) == 0
    assert "[assets] openverse: no results" in capsys.readouterr().err


def test_source_with_only_unusable_results_is_reported(net, tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("PEXELS_API_KEY", "PK")
    px = fixture("pexels")
    for p in px["photos"]:
        p["width"] = 500
    net["override"] = {"pexels": px}
    assert search(tmp_path) == 0
    err = capsys.readouterr().err
    assert "[assets] pexels: 2 results, 0 usable" in err
    assert "[assets] openverse:" not in err  # a source that contributed candidates stays quiet


def test_source_whose_thumbnails_all_fail_is_reported(net, tmp_path, monkeypatch, capsys):
    real = netutil.get_bytes

    def flaky(url, **kw):
        if "openverse.org" in url:
            raise netutil.NetError(f"{url} -> HTTP 424")
        return real(url, **kw)

    monkeypatch.setattr(netutil, "get_bytes", flaky)
    assert search(tmp_path) == 0
    assert "[assets] openverse: 2 results, 0 usable" in capsys.readouterr().err


def test_hits_counts_every_response_shape():
    assert assets._hits(fixture("openverse")) == 2 and assets._hits(fixture("wikimedia")) == 2
    assert assets._hits(fixture("pexels")) == 2 and assets._hits(fixture("pixabay")) == 2
    assert assets._hits({}) == 0 and assets._hits([]) == 0 and assets._hits({"query": None}) == 0


def test_credits_files_flag_prefixes_the_file(tmp_path, capsys):
    base = {"author_url": None, "landing_url": "https://x/land", "license_url": "https://x/lic", "ai_risk": False,
            "fetched": "2026-10-01"}
    d = write_credits(tmp_path, [
        dict(base, file="a.jpg", source="pexels", title="Rocks", author="Joey", license="Pexels License",
             attribution_required=False),
        dict(base, file="b.jpg", source="wikimedia", title="Squirrel", author="Sharp", license="CC BY 4.0",
             attribution_required=True),
        dict(base, file="g.jpg", source="gen:cloudflare", title="p", author="AI-generated", license="Apache-2.0",
             attribution_required=False, ai_generated=True, provider="cloudflare", model="m"),
        dict(base, file="icons/x.svg", source="iconify", title="lucide:x", author="L", license="ISC",
             attribution_required=False),
    ])
    assert assets.main(["credits", str(d), "--files"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "b.jpg: * Photo: \"Squirrel\" by Sharp, Wikimedia Commons, CC BY 4.0 (https://x/lic) https://x/land",
        "a.jpg: Photo: \"Rocks\" by Joey, Pexels, Pexels License",
        "g.jpg: AI-generated image (FLUX.1-schnell via Cloudflare Workers AI)"]
    assert assets.main(["credits", str(d)]) == 0  # default output unchanged
    assert not any(line.startswith(("a.jpg:", "b.jpg:")) for line in capsys.readouterr().out.splitlines())


def test_get_saves_a_big_flat_download_as_jpeg(net, tmp_path):
    buf = io.BytesIO()
    im = Image.new("RGB", (2400, 1400), (200, 210, 230))  # few colors: kind_guess says screenshot
    im.paste((90, 120, 80), (600, 300, 1800, 1100))
    im.save(buf, "PNG")
    net["full"] = buf.getvalue()
    search(tmp_path)
    assert get(tmp_path, "wikimedia:47900137") == 0
    index = json.loads((tmp_path / "assets" / "images.json").read_text(encoding="utf-8"))
    assert list(index) == ["wikimedia-47900137.jpg"] and index["wikimedia-47900137.jpg"]["kind_guess"] == "screenshot"


def test_get_refuses_a_huge_download_without_decoding_it(net, tmp_path, capsys):
    buf = io.BytesIO()
    Image.new("1", (10001, 10001)).save(buf, "PNG")  # 100 MP, tiny on disk
    net["full"] = buf.getvalue()
    search(tmp_path)
    capsys.readouterr()
    assert get(tmp_path, "wikimedia:47900137") == 1
    assert "[assets] could not process wikimedia:47900137" in capsys.readouterr().err
    assert not (tmp_path / "assets" / "credits.json").exists()
