import io
import json
import os
import sys
import zipfile
from functools import lru_cache
from pathlib import Path

import pytest

import deckkit.fonts as dkfonts
import fonts as fonts_cli
import netutil


@lru_cache(maxsize=1)
def _small_ttf():
    """Bytes of the smallest installed .ttf (any font will do: only the file name matters to install)."""
    paths = [Path(p) for styles in dkfonts.installed_fonts().values() for p, _ in styles.values() if p.lower().endswith(".ttf")]
    if not paths:
        pytest.skip("no installed .ttf to use as a fixture")
    return min(paths, key=lambda p: p.stat().st_size).read_bytes()


def _zip(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in members.items():
            z.writestr(name, data)
    return buf.getvalue()


def _entry(**dl):
    return {"id": "test", "family": "Test", "scripts": ["latin"], "roles": ["body"], "category": "sans", "license": "OFL-1.1",
            "download": dl, "official_url": "https://example.com/test", "noonnu_url": None, "verified_on": "2026-10-01"}


@pytest.fixture
def catalog(monkeypatch):
    def use(entry):
        monkeypatch.setattr(fonts_cli, "load_catalog", lambda: [entry])
    return use


def _github(monkeypatch, zdata):
    release = {"tag_name": "v1", "assets": [{"name": "Other-1.zip", "browser_download_url": "https://x/other.zip"},
                                           {"name": "Test-1.zip", "browser_download_url": "https://x/test.zip"}]}
    seen = {}

    def get_json(url, **kw):
        seen["json"] = (url, kw)
        return release

    def get_bytes(url, **kw):
        seen["bytes"] = url
        return zdata

    monkeypatch.setattr(netutil, "get_json", get_json)
    monkeypatch.setattr(netutil, "get_bytes", get_bytes)
    return seen


def test_github_install_dest_copies_only_wanted_style(monkeypatch, catalog, tmp_path, capsys):
    ttf = _small_ttf()
    seen = _github(monkeypatch, _zip({"x/static/Test-Regular.ttf": ttf, "x/static/Test-Thin.ttf": ttf,
                                      "x/static/Test-Regular.otf": b"otf", "x/other/Test-Bold.ttf": ttf}))
    catalog(_entry(type="github_release", repo="o/test", asset="Test-*.zip", members="x/static/*", styles=["Regular"]))
    dest = tmp_path / "out"
    assert fonts_cli.main(["install", "test", "--dest", str(dest)]) == 0
    assert sorted(p.name for p in dest.iterdir()) == ["Test-Regular.ttf"]
    cap = capsys.readouterr()
    assert "Test-Regular.otf" in cap.err and "only .ttf" in cap.err    # .otf skipped with a note (stderr)
    assert "Restart PowerPoint" not in cap.out                         # --dest is a copy only
    assert seen["json"][0] == "https://api.github.com/repos/o/test/releases/latest"
    assert seen["json"][1]["headers"]["Accept"] == "application/vnd.github+json"
    assert seen["bytes"] == "https://x/test.zip"                       # matched the asset glob, not Other-1.zip


def test_zip_slip_only_basename_is_used(monkeypatch, catalog, tmp_path):
    _github(monkeypatch, _zip({"x/static/../../Evil-Regular.ttf": _small_ttf()}))
    catalog(_entry(type="github_release", repo="o/test", asset="Test-*.zip", members="*.ttf", styles=["Regular"]))
    dest = tmp_path / "a" / "out"
    assert fonts_cli.main(["install", "test", "--dest", str(dest)]) == 0
    assert [p.name for p in dest.iterdir()] == ["Evil-Regular.ttf"]
    assert not (tmp_path / "Evil-Regular.ttf").exists() and not (tmp_path / "a" / "Evil-Regular.ttf").exists()


def test_github_no_matching_members_fails(monkeypatch, catalog, tmp_path, capsys):
    _github(monkeypatch, _zip({"x/readme.txt": b"hi"}))
    catalog(_entry(type="github_release", repo="o/test", asset="Test-*.zip", members="x/static/*.ttf"))
    assert fonts_cli.main(["install", "test", "--dest", str(tmp_path / "o")]) == 1
    assert "no installable .ttf" in capsys.readouterr().err


def test_google_manifest_strips_prefix_and_filters():
    body = b")]}'\n" + json.dumps({"manifest": {"fileRefs": [
        {"filename": "static/Test-Regular.ttf", "url": "https://fonts.gstatic.com/r"},
        {"filename": "static/Test-Thin.ttf", "url": "https://fonts.gstatic.com/t"},
        {"filename": "static/Test_Condensed-Regular.ttf", "url": "https://fonts.gstatic.com/c"},
        {"filename": "Test-VariableFont_wght.ttf", "url": "https://fonts.gstatic.com/v"},
        {"filename": "Test-Bold.ttf", "url": "https://fonts.gstatic.com/b"},          # no static/ folder: root files count
        {"filename": "OFL.txt", "url": "https://fonts.gstatic.com/o"}]}}).encode()
    refs = fonts_cli.google_manifest(body)
    picked = fonts_cli.google_pick(refs, {"family": "Test", "styles": ["Regular", "Bold"]})
    assert [r["filename"] for r in picked] == ["static/Test-Regular.ttf", "Test-Bold.ttf"]
    stem = fonts_cli.google_pick(refs, {"family": "Test", "stem": "Test_Condensed", "styles": ["Regular"]})
    assert [r["filename"] for r in stem] == ["static/Test_Condensed-Regular.ttf"]


def test_google_install(monkeypatch, catalog, tmp_path):
    ttf = _small_ttf()
    manifest = b")]}'\n" + json.dumps({"manifest": {"fileRefs": [
        {"filename": "static/TestSans-Regular.ttf", "url": "https://fonts.gstatic.com/r"},
        {"filename": "static/TestSans-Thin.ttf", "url": "https://fonts.gstatic.com/t"}]}}).encode()
    urls = []

    def get_bytes(url, **kw):
        urls.append(url)
        return manifest if "download/list" in url else ttf

    monkeypatch.setattr(netutil, "get_bytes", get_bytes)
    catalog(_entry(type="google_fonts", family="Test Sans", styles=["Regular"]))
    assert fonts_cli.main(["install", "test", "--dest", str(tmp_path / "o")]) == 0
    assert urls[0] == "https://fonts.google.com/download/list?family=Test%20Sans"
    assert [p.name for p in (tmp_path / "o").iterdir()] == ["TestSans-Regular.ttf"]
    assert urls[1:] == ["https://fonts.gstatic.com/r"]                 # the Thin file was never downloaded


def test_manual_entry_exits_1_with_link(catalog, capsys, tmp_path):
    catalog(_entry(type="manual"))
    assert fonts_cli.main(["install", "test", "--dest", str(tmp_path / "o")]) == 1
    err = capsys.readouterr().err
    assert "https://example.com/test" in err and "install manually" in err and "restart PowerPoint" in err
    assert not (tmp_path / "o").exists()


def test_unknown_id_exits_2(capsys):
    assert fonts_cli.main(["install", "no-such-font-id"]) == 2
    assert "unknown font id" in capsys.readouterr().err


def test_rate_limited_message(monkeypatch, catalog, capsys, tmp_path):
    def boom(*a, **k):
        raise netutil.RateLimited("api.github.com: rate limited")

    monkeypatch.setattr(netutil, "get_json", boom)
    catalog(_entry(type="github_release", repo="o/test", asset="Test-*.zip", members="*.ttf"))
    assert fonts_cli.main(["install", "test", "--dest", str(tmp_path / "o")]) == 1
    err = capsys.readouterr().err
    assert err.startswith("[fonts]") and "60" in err and "https://example.com/test" in err


def test_rate_limited_message_google(monkeypatch, catalog, capsys, tmp_path):
    def boom(*a, **k):
        raise netutil.RateLimited("fonts.google.com: rate limited")

    monkeypatch.setattr(netutil, "get_bytes", boom)
    catalog(_entry(type="google_fonts", family="Test", styles=["Regular"]))
    assert fonts_cli.main(["install", "test", "--dest", str(tmp_path / "o")]) == 1
    err = capsys.readouterr().err
    assert "Google Fonts" in err and "GitHub" not in err


def test_net_error_exits_1(monkeypatch, catalog, capsys, tmp_path):
    def boom(*a, **k):
        raise netutil.NetError("x -> HTTP 500")

    monkeypatch.setattr(netutil, "get_bytes", boom)
    catalog(_entry(type="google_fonts", family="Test", styles=["Regular"]))
    assert fonts_cli.main(["install", "test", "--dest", str(tmp_path / "o")]) == 1
    assert "download failed" in capsys.readouterr().err


def test_existing_same_size_file_is_not_rewritten(monkeypatch, catalog, tmp_path):
    _github(monkeypatch, _zip({"x/Test-Regular.ttf": _small_ttf()}))
    catalog(_entry(type="github_release", repo="o/test", asset="Test-*.zip", members="x/*.ttf", styles=["Regular"]))
    dest = tmp_path / "o"
    assert fonts_cli.main(["install", "test", "--dest", str(dest)]) == 0
    f = dest / "Test-Regular.ttf"
    os.utime(f, (1_000_000, 1_000_000))
    assert fonts_cli.main(["install", "test", "--dest", str(dest)]) == 0
    assert int(f.stat().st_mtime) == 1_000_000


def test_real_install_registers_and_clears_cache(monkeypatch, catalog, tmp_path):
    """No --dest: files go to the per-user dir (patched to tmp), the registry hook runs on Windows, the font cache is cleared."""
    _github(monkeypatch, _zip({"x/Test-Regular.ttf": _small_ttf()}))
    catalog(_entry(type="github_release", repo="o/test", asset="Test-*.zip", members="x/*.ttf", styles=["Regular"]))
    user_dir = tmp_path / "userfonts"
    registered = []
    monkeypatch.setattr(fonts_cli, "user_font_dir", lambda: user_dir)
    monkeypatch.setattr(fonts_cli, "_register_windows", lambda dst, family, style: registered.append((dst.name, style)))
    monkeypatch.setattr(fonts_cli, "_broadcast_font_change", lambda: None)
    monkeypatch.setattr(fonts_cli.subprocess, "run", lambda *a, **k: None)
    cleared = []
    fake = lambda: {}  # noqa: E731
    fake.cache_clear = lambda: cleared.append(1)
    monkeypatch.setattr(dkfonts, "installed_fonts", fake)
    assert fonts_cli.main(["install", "test"]) == 0
    assert (user_dir / "Test-Regular.ttf").exists() and cleared == [1]
    if os.name == "nt":
        assert registered and registered[0][0] == "Test-Regular.ttf"


def test_catalog_json_marks_installed(monkeypatch, capsys):
    monkeypatch.setattr(dkfonts, "installed_fonts", lambda: {"Pretendard": {"Regular": ("x.ttf", 0)}})
    assert fonts_cli.main(["catalog", "--json"]) == 0
    rows = {r["id"]: r for r in json.loads(capsys.readouterr().out)}
    assert rows["pretendard"]["installed"] is True and rows["suit"]["installed"] is False


def test_catalog_filters(capsys):
    fonts_cli.main(["catalog", "--script", "latin", "--role", "mono", "--json"])
    rows = json.loads(capsys.readouterr().out)
    assert rows and all("latin" in r["scripts"] and "mono" in r["roles"] for r in rows)
    assert {"jetbrains-mono", "ibm-plex-mono"} <= {r["id"] for r in rows}


def test_catalog_text_output(capsys):
    fonts_cli.main(["catalog", "--role", "mono"])
    assert "jetbrains-mono" in capsys.readouterr().out


def test_fonts_json_is_consistent():
    entries = json.loads(fonts_cli.CATALOG.read_text(encoding="utf-8"))
    ids = [e["id"] for e in entries]
    assert len(ids) == len(set(ids))
    required = {"pretendard", "wanted-sans", "suit","ibm-plex-sans-kr", "noto-sans-kr", "gothic-a1",
                "noto-serif-kr", "nanum-myeongjo", "hahmlet", "gowun-batang", "black-han-sans", "do-hyeon", "jetbrains-mono",
                "ibm-plex-mono", "d2coding", "ibm-plex-sans", "source-serif-4", "work-sans", "fraunces", "gmarket-sans",
                "line-seed-sans-kr", "paperlogy", "nanum-square-neo"}
    assert required <= set(ids)
    banned = {"inter", "roboto", "poppins", "montserrat", "space grotesk", "instrument serif", "geist"}
    assert not any(e["family"].lower() in banned for e in entries)
    for e in entries:
        assert e["official_url"].startswith("https://")
        dl = e["download"]
        assert dl["type"] in ("github_release", "google_fonts", "manual")
        if dl["type"] == "github_release":
            assert dl["repo"] and dl["asset"] and dl["members"].endswith(".ttf")
        if dl["type"] == "google_fonts":
            assert dl["family"] and dl["styles"]


def test_reg_name():
    assert fonts_cli._reg_name("Pretendard", "Regular") == "Pretendard (TrueType)"
    assert fonts_cli._reg_name("Pretendard", "Bold") == "Pretendard Bold (TrueType)"


class _FakeWinreg:
    """In-memory winreg: records CreateKeyEx args; never touches the real registry."""
    HKEY_CURRENT_USER = "HKCU"
    KEY_SET_VALUE = 2
    KEY_QUERY_VALUE = 1
    REG_SZ = 1

    def __init__(self, values=None):
        self.values = dict(values or {})
        self.created = []

    def CreateKeyEx(self, root, sub, reserved, access):
        self.created.append((root, sub, access))
        return self

    def QueryValueEx(self, key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        return self.values[name], self.REG_SZ

    def SetValueEx(self, key, name, reserved, typ, value):
        self.values[name] = value

    def CloseKey(self, key):
        pass


def test_register_windows_uses_createkeyex_and_keeps_foreign_values(monkeypatch, tmp_path):
    fake = _FakeWinreg({"Other (TrueType)": r"C:\elsewhere\Other.ttf"})
    monkeypatch.setitem(sys.modules, "winreg", fake)
    dst = tmp_path / "Test-Bold.ttf"
    fonts_cli._register_windows(dst, "Test", "Bold")
    assert fake.created[0][:2] == ("HKCU", r"Software\Microsoft\Windows NT\CurrentVersion\Fonts")
    assert fake.values["Test Bold (TrueType)"] == str(dst)
    fonts_cli._register_windows(dst, "Test", "Bold")                   # same file again: fine
    fake.values["Test (TrueType)"] = r"C:\elsewhere\Test.ttf"
    with pytest.raises(FileExistsError):
        fonts_cli._register_windows(tmp_path / "Test-Regular.ttf", "Test", "Regular")
    assert fake.values["Test (TrueType)"] == r"C:\elsewhere\Test.ttf"  # never overwritten


def _fake_installed(table, cleared=None):
    fake = lambda: table  # noqa: E731
    fake.cache_clear = (lambda: cleared.append(1)) if cleared is not None else (lambda: None)
    return fake


def _real_setup(monkeypatch, catalog, tmp_path, installed=None, **dl):
    """Real-install path (no --dest) with every side effect patched: user font dir -> tmp, no registry/ctypes/fc-cache."""
    _github(monkeypatch, _zip({"x/Test-Regular.ttf": _small_ttf()}))
    catalog(_entry(type="github_release", repo="o/test", asset="Test-*.zip", members="x/*.ttf", **dl))
    user_dir = tmp_path / "userfonts"
    monkeypatch.setattr(fonts_cli, "user_font_dir", lambda: user_dir)
    monkeypatch.setattr(fonts_cli, "_broadcast_font_change", lambda: None)
    monkeypatch.setattr(fonts_cli, "_load_font", lambda dst: None)
    monkeypatch.setattr(fonts_cli, "_register_windows", lambda dst, family, style: None)  # never the real registry
    monkeypatch.setattr(fonts_cli.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(dkfonts, "installed_fonts", _fake_installed(installed or {}))
    monkeypatch.setattr(sys, "executable", "python")
    return user_dir


def test_family_style_installed_elsewhere_is_skipped(monkeypatch, catalog, tmp_path, capsys):
    from PIL import ImageFont
    user_dir = _real_setup(monkeypatch, catalog, tmp_path, styles=["Regular"])
    probe = tmp_path / "probe.ttf"
    probe.write_bytes(_small_ttf())
    family, style = ImageFont.truetype(str(probe), 12).getname()
    other = str(tmp_path / "elsewhere" / "Other.ttf")
    monkeypatch.setattr(dkfonts, "installed_fonts", _fake_installed({family: {style: (other, 0)}}))
    assert fonts_cli.main(["install", "test"]) == 0
    assert f"already installed at {other}" in capsys.readouterr().out
    assert not list(user_dir.glob("*.ttf"))


def test_all_styles_present_returns_early_without_network(monkeypatch, catalog, tmp_path, capsys):
    _real_setup(monkeypatch, catalog, tmp_path, installed={"Test": {"Regular": ("x.ttf", 0)}}, styles=["Regular"])

    def boom(*a, **k):
        raise AssertionError("must not touch the network")

    monkeypatch.setattr(netutil, "get_json", boom)
    monkeypatch.setattr(netutil, "get_bytes", boom)
    assert fonts_cli.main(["install", "test"]) == 0
    assert "already installed" in capsys.readouterr().out


def test_microsoft_store_python_gets_manual_instructions(monkeypatch, catalog, tmp_path, capsys):
    _real_setup(monkeypatch, catalog, tmp_path, styles=["Regular"])
    monkeypatch.setattr(sys, "executable", r"C:\Program Files\WindowsApps\PythonSoftwareFoundation\python.exe")

    def boom(*a, **k):
        raise AssertionError("must not download")

    monkeypatch.setattr(netutil, "get_json", boom)
    assert fonts_cli.main(["install", "test"]) == 1
    err = capsys.readouterr().err
    assert "Microsoft Store" in err and "https://example.com/test" in err
    assert not (tmp_path / "userfonts").exists()


def test_store_python_does_not_block_dest(monkeypatch, catalog, tmp_path):
    _real_setup(monkeypatch, catalog, tmp_path, styles=["Regular"])
    monkeypatch.setattr(sys, "executable", r"C:\x\WindowsApps\python.exe")
    assert fonts_cli.main(["install", "test", "--dest", str(tmp_path / "o")]) == 0


@pytest.mark.skipif(os.name != "nt", reason="registration runs on Windows only")
def test_failed_registration_deletes_copied_file(monkeypatch, catalog, tmp_path, capsys):
    user_dir = _real_setup(monkeypatch, catalog, tmp_path, styles=["Regular"])

    def fail(dst, family, style):
        raise PermissionError("denied")

    monkeypatch.setattr(fonts_cli, "_register_windows", fail)
    assert fonts_cli.main(["install", "test"]) == 1
    assert not list(user_dir.glob("*"))
    assert "could not install" in capsys.readouterr().err


def test_copy_is_atomic_and_leaves_no_part_file(tmp_path):
    src = tmp_path / "a.ttf"
    src.write_bytes(b"data")
    dst = tmp_path / "out" / "a.ttf"
    dst.parent.mkdir()
    fonts_cli._copy_atomic(src, dst)
    assert dst.read_bytes() == b"data" and [p.name for p in dst.parent.iterdir()] == ["a.ttf"]


def test_macos_resource_fork_files_are_skipped(monkeypatch, catalog, tmp_path, capsys):
    _github(monkeypatch, _zip({"x/Test-Regular.ttf": _small_ttf(), "x/._Test-Regular.ttf": b"junk"}))
    catalog(_entry(type="github_release", repo="o/test", asset="Test-*.zip", members="x/*.ttf"))
    assert fonts_cli.main(["install", "test", "--dest", str(tmp_path / "o")]) == 0
    assert [p.name for p in (tmp_path / "o").iterdir()] == ["Test-Regular.ttf"]
    assert "._Test" not in capsys.readouterr().err


def test_note_is_shown_in_catalog(capsys):
    fonts_cli.main(["catalog", "--json"])
    rows = {r["id"]: r for r in json.loads(capsys.readouterr().out)}
    assert "fsType 4" in rows["suit"]["note"] and "note" not in rows["pretendard"]
    fonts_cli.main(["catalog", "--role", "head"])
    assert "fsType 4" in capsys.readouterr().out


@pytest.mark.skipif(os.name != "nt", reason="registration runs on Windows only")
def test_failed_registration_keeps_a_file_that_existed_before(monkeypatch, catalog, tmp_path):
    user_dir = _real_setup(monkeypatch, catalog, tmp_path, styles=["Regular"])
    user_dir.mkdir()
    old = user_dir / "Test-Regular.ttf"
    old.write_bytes(b"older, different size")

    def fail(dst, family, style):
        raise PermissionError("denied")

    monkeypatch.setattr(fonts_cli, "_register_windows", fail)
    assert fonts_cli.main(["install", "test"]) == 1
    assert old.exists()
