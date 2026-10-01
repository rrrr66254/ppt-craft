import json
import sys
import urllib.parse
from pathlib import Path

import pytest
from PIL import Image

import assets
import netutil
from deckkit.svg import UNSAFE_SVG

FIX = Path(__file__).parent / "fixtures" / "net"


def fixture(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


CIRCLE = ('<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" viewBox="0 0 24 24">'
          '<circle cx="12" cy="12" r="8" fill="{c}"/></svg>')


@pytest.fixture
def net(monkeypatch):
    """Fake netutil for Iconify: records calls; the fake SVG honours the requested color/height like the real API."""
    state = {"json": [], "bytes": []}

    def fake_json(url, *, headers=None, cache_dir=None, ttl=86400):
        state["json"].append(url)
        path = urllib.parse.urlsplit(url).path
        return fixture("iconify_search" if path == "/search" else "iconify_collections")

    def fake_bytes(url, *, headers=None, timeout=60, max_bytes=50_000_000):
        state["bytes"].append(url)
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        return CIRCLE.format(s=q["height"][0], c=q["color"][0]).encode()

    monkeypatch.setattr(netutil, "get_json", fake_json)
    monkeypatch.setattr(netutil, "get_bytes", fake_bytes)
    return state


def search(*extra):
    return assets.main(["icon", "search", "database", "--cache", "unused", *extra])


def test_search_keeps_allowed_sets_drops_blocked_and_unlisted(net, capsys):
    assert search() == 0
    out = capsys.readouterr().out.splitlines()
    assert out == ["lucide:database  ISC", "tabler:database  MIT", "mdi:database  Apache-2.0", "lucide:database-zap  ISC"]
    req = urllib.parse.urlsplit(net["json"][0])
    q = urllib.parse.parse_qs(req.query)
    assert req.netloc == "api.iconify.design" and q["query"] == ["database"] and q["limit"] == ["32"]
    assert "openmoji" not in q["prefixes"][0] and "simple-icons" not in q["prefixes"][0]
    assert q["prefixes"][0].split(",") == ["lucide", "tabler", "ph", "material-symbols", "fluent", "heroicons", "carbon", "mdi"]
    coll = urllib.parse.parse_qs(urllib.parse.urlsplit(net["json"][1]).query)
    assert coll["prefixes"] == ["lucide,mdi,tabler"]  # only the sets present in the result


def test_search_license_gate_drops_disallowed_license_even_if_set_is_listed(net, monkeypatch, capsys):
    monkeypatch.setitem(assets.SOURCES, "icon_sets_allowed", assets.SOURCES["icon_sets_allowed"] + ["fa6-solid", "openmoji"])
    monkeypatch.setitem(assets.SOURCES, "icon_sets_blocked", ["simple-icons", "logos"])  # openmoji only excluded by license now
    assert search() == 0
    ids = [line.split()[0] for line in capsys.readouterr().out.splitlines()]
    assert "fa6-solid:database" not in ids and "openmoji:database" not in ids
    assert {"lucide:database", "tabler:database", "mdi:database"} <= set(ids)


def test_search_json_limit_and_sets(net, capsys):
    assert search("--json", "--limit", "2", "--sets", "lucide,tabler") == 0
    data = json.loads(capsys.readouterr().out)
    assert data == [{"id": "lucide:database", "license": "ISC"}, {"id": "tabler:database", "license": "MIT"}]
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(net["json"][0]).query)
    assert q["prefixes"] == ["lucide,tabler"] and q["limit"] == ["32"]  # limit is never requested below 32


def test_search_blocked_or_unknown_set_exits_2(net, capsys):
    assert search("--sets", "openmoji") == 2
    assert "openmoji" in capsys.readouterr().err
    assert search("--sets", "lucide,simple-icons") == 2
    assert search("--limit", "0") == 2
    assert not net["json"]


def test_search_net_error_exits_1(monkeypatch, capsys):
    def boom(url, **kw):
        raise netutil.RateLimited("api.iconify.design: rate limited")

    monkeypatch.setattr(netutil, "get_json", boom)
    assert search() == 1
    assert "[assets] icon search failed: api.iconify.design: rate limited" in capsys.readouterr().err


def get(tmp_path, icon_id="lucide:circle", color="#FF0000", *extra):
    return assets.main(["icon", "get", icon_id, "--color", color, "--out", str(tmp_path / "assets" / "icons"),
                        "--cache", "unused", *extra])


def test_get_writes_svg_png_and_credit(net, tmp_path, capsys):
    assert get(tmp_path, "lucide:circle", "#FF0000", "--size", "64") == 0
    icons = tmp_path / "assets" / "icons"
    svg = (icons / "lucide-circle.svg").read_text(encoding="utf-8")
    assert 'fill="#FF0000"' in svg
    im = Image.open(icons / "lucide-circle.png").convert("RGBA")
    assert im.size == (64, 64)
    assert im.getpixel((32, 32)) == (255, 0, 0, 255)  # centre of the filled circle is the requested color
    assert im.getpixel((1, 1))[3] == 0  # outside the circle stays transparent
    url = urllib.parse.urlsplit(net["bytes"][0])
    assert url.path == "/lucide/circle.svg" and urllib.parse.parse_qs(url.query) == {"color": ["#FF0000"], "height": ["64"]}
    assert "color=%23FF0000" in net["bytes"][0]
    credits = json.loads((tmp_path / "assets" / "credits.json").read_text(encoding="utf-8"))
    assert len(credits) == 1
    rec = credits[0]
    assert (rec["file"], rec["source"], rec["license"], rec["attribution_required"]) == (
        "icons/lucide-circle.svg", "iconify", "ISC", False)
    assert rec["landing_url"] == "https://icon-sets.iconify.design/lucide/circle/"
    assert "lucide-circle.svg" in capsys.readouterr().out


def test_get_again_replaces_credit_and_credits_cmd_hides_icons(net, tmp_path, capsys):
    get(tmp_path)
    get(tmp_path, "lucide:circle", "#00FF00")
    get(tmp_path, "tabler:circle", "#00FF00")
    credits = json.loads((tmp_path / "assets" / "credits.json").read_text(encoding="utf-8"))
    assert sorted(c["file"] for c in credits) == ["icons/lucide-circle.svg", "icons/tabler-circle.svg"]
    capsys.readouterr()
    assert assets.main(["credits", str(tmp_path / "assets")]) == 0
    assert capsys.readouterr().out == ""  # icons carry no credit line


def test_get_blocked_or_unlisted_set_refused_exit_1(net, tmp_path, capsys):
    for icon in ("simple-icons:mongodb", "openmoji:database", "fa6-solid:database"):
        assert get(tmp_path, icon) == 1
        assert "refused" in capsys.readouterr().err
    assert not net["bytes"] and not (tmp_path / "assets").exists()


def test_get_listed_set_with_bad_license_refused(net, tmp_path, monkeypatch, capsys):
    monkeypatch.setitem(assets.SOURCES, "icon_sets_allowed", assets.SOURCES["icon_sets_allowed"] + ["fa6-solid"])
    assert get(tmp_path, "fa6-solid:database") == 1
    assert "license CC-BY-4.0" in capsys.readouterr().err and not net["bytes"]


@pytest.mark.parametrize("color", ["red", "#FFF", "#GGGGGG", "FF0000", "#FF00000", "#ff0000; x"])
def test_bad_color_exits_2(net, tmp_path, color):
    assert get(tmp_path, "lucide:circle", color) == 2
    assert not net["bytes"]


@pytest.mark.parametrize("icon", ["lucide", "Lucide:Circle", "lucide:../x", "a:b:c", ""])
def test_bad_icon_id_exits_2(net, tmp_path, icon):
    assert get(tmp_path, icon) == 2


def test_bad_size_exits_2(net, tmp_path):
    assert get(tmp_path, "lucide:circle", "#FF0000", "--size", "8") == 2


def test_resvg_missing_exits_1(net, tmp_path, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "resvg_py", None)  # makes `import resvg_py` raise ImportError
    assert get(tmp_path) == 1
    assert "[assets] resvg-py missing: pip install -r requirements.txt" in capsys.readouterr().err
    assert not net["bytes"]


def test_get_non_svg_response_exits_1(net, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(netutil, "get_bytes", lambda url, **kw: b"<html>nope</html>")
    assert get(tmp_path) == 1
    assert "did not return an SVG" in capsys.readouterr().err
    assert not (tmp_path / "assets").exists()


def test_get_download_error_exits_1(net, tmp_path, monkeypatch, capsys):
    def boom(url, **kw):
        raise netutil.NetError(f"{url} -> HTTP 404")

    monkeypatch.setattr(netutil, "get_bytes", boom)
    assert get(tmp_path) == 1
    assert "[assets] icon download failed" in capsys.readouterr().err


UNSAFE = [
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><script>alert(1)</script></svg>',
    '<svg viewBox="0 0 24 24"><SCRIPT src="x"></SCRIPT></svg>',
    '<svg viewBox="0 0 24 24"><image href="data:image/png;base64,AAAA"/></svg>',
    '<svg viewBox="0 0 24 24"><foreignObject><div/></foreignObject></svg>',
    '<svg viewBox="0 0 24 24"><use href="https://evil.example/a.svg#x"/></svg>',
    '<svg xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 24 24"><use xlink:href=\'http://evil.example/a.svg#x\'/></svg>',
    '<svg viewBox="0 0 24 24"><path fill="url(https://evil.example/a.svg#g)" d="M0 0"/></svg>',
    '<svg viewBox="0 0 24 24"><path style="fill: url( \'http://evil.example/x\')" d="M0 0"/></svg>',
    '<svg viewBox="0 0 24 24" onload="alert(1)"><path d="M0 0"/></svg>',
]


@pytest.mark.parametrize("svg", UNSAFE)
def test_get_refuses_svgs_with_scripts_or_external_references(net, tmp_path, monkeypatch, capsys, svg):
    monkeypatch.setattr(netutil, "get_bytes", lambda url, **kw: svg.encode())
    assert get(tmp_path) == 1
    assert "[assets] icon refused: lucide:circle contains external references or scripts" in capsys.readouterr().err
    assert not (tmp_path / "assets").exists()  # nothing written, no credit


def test_get_allows_local_fragment_references(net, tmp_path, monkeypatch):
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 24 24">'
           '<defs><linearGradient id="g"><stop offset="0" stop-color="#f00"/></linearGradient><path id="p" d="M0 0h24v24H0z"/></defs>'
           '<use xlink:href="#p" fill="url(#g)"/><path fill="url( #g )" d="M1 1h4v4H1z"/></svg>')
    monkeypatch.setattr(netutil, "get_bytes", lambda url, **kw: svg.encode())
    assert get(tmp_path) == 0


def test_real_iconify_style_svg_is_not_flagged():
    real = ('<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 24 24"><g fill="none" stroke="#FF0000" '
            'stroke-linecap="round" stroke-linejoin="round" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/>'
            '<path d="M3 5v14a9 3 0 0 0 18 0V5"/></g></svg>')
    assert not UNSAFE_SVG.search(real)


def test_png_is_rendered_by_height_only_keeping_aspect(net, tmp_path, monkeypatch):
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 24"><rect width="12" height="24" fill="#FF0000"/></svg>'
    monkeypatch.setattr(netutil, "get_bytes", lambda url, **kw: svg.encode())
    assert get(tmp_path, "lucide:circle", "#FF0000", "--size", "64") == 0
    assert Image.open(tmp_path / "assets" / "icons" / "lucide-circle.png").size == (32, 64)
