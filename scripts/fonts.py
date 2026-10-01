"""Installed-font lookup, curated free-font catalog, per-user font install.
Usage:
  python fonts.py list [--hangul] [--grep NAME]     installed fonts as JSON [{"family": ..., "styles": [...]}]
  python fonts.py catalog [--script ko|latin] [--role head|body|mono] [--json]   curated fonts (+ "installed": bool)
  python fonts.py install <id> [--dest DIR]         download + install for the current user (no admin rights);
                                                    --dest copies only (no registry, for tests)
Exit codes: 0 ok, 1 failed / manual entry, 2 bad usage. All HTTP goes through netutil."""
import argparse
import fnmatch
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import netutil  # noqa: E402
import deckkit.fonts as dkfonts  # noqa: E402
from deckkit.fonts import find_font_file, has_hangul, installed_fonts  # noqa: E402
from PIL import ImageFont  # noqa: E402

CATALOG = Path(__file__).resolve().parents[1] / "data" / "fonts.json"
ZIP_MAX = 150_000_000       # largest release zip we download (Pretendard is 47 MB)
MEMBER_MAX = 100_000_000    # per-file cap when extracting (zip-bomb guard)


def _err(msg):
    print(f"[fonts] {msg}", file=sys.stderr)


def load_catalog():
    return json.loads(CATALOG.read_text(encoding="utf-8"))


# ---------- download recipes: each returns paths of .ttf files written into tmp ----------

def _style_of(filename):
    """'NotoSansKR-Bold.ttf' -> 'Bold' (the word after the last '-')."""
    return PurePosixPath(filename).stem.rpartition("-")[2]


def _write_member(name, data, tmp, notes):
    """Only the basename is ever used (no zip-slip); non-.ttf is skipped with a note."""
    base = PurePosixPath(name).name
    if base.startswith("._"):  # macOS resource-fork junk inside zips
        return None
    if not base.lower().endswith(".ttf"):
        notes.append(f"skipped {base} (only .ttf is installed)")
        return None
    out = Path(tmp) / base
    out.write_bytes(data)
    return out


def _from_zip(data, members, styles, tmp, notes):
    out = []
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise netutil.NetError("downloaded file is not a valid zip")
    for info in z.infolist():
        name = info.filename.replace("\\", "/")
        if info.is_dir() or not fnmatch.fnmatchcase(name, members):
            continue
        if styles and _style_of(name) not in styles:
            continue
        if info.file_size > MEMBER_MAX:
            notes.append(f"skipped {name} (too large)")
            continue
        p = _write_member(name, z.read(info), tmp, notes)
        if p:
            out.append(p)
    return out


def _github_release(dl, tmp, notes):
    rel = netutil.get_json(f"https://api.github.com/repos/{dl['repo']}/releases/latest",
                           headers={"Accept": "application/vnd.github+json"})
    asset = next((a for a in rel.get("assets", []) if fnmatch.fnmatchcase(a["name"], dl["asset"])), None)
    if asset is None:
        raise netutil.NetError(f"{dl['repo']} release {rel.get('tag_name')}: no asset matches {dl['asset']}")
    data = netutil.get_bytes(asset["browser_download_url"], max_bytes=ZIP_MAX)
    return _from_zip(data, dl["members"], dl.get("styles"), tmp, notes)


def google_manifest(body):
    """download/list response: strip the )]}' prefix, parse JSON, return manifest.fileRefs."""
    text = body.decode("utf-8") if isinstance(body, bytes) else body
    if text.startswith(")]}'"):
        text = text[4:]
    return json.loads(text)["manifest"]["fileRefs"]


def google_pick(refs, dl):
    """Static .ttf of the wanted styles, from the zip root or static/ (variable fonts are skipped).
    `stem` (default: family without spaces) must equal the file name before the style, which drops optical-size / width cuts."""
    stem = dl.get("stem") or dl["family"].replace(" ", "")
    picked = []
    for r in refs:
        folder, _, base = r["filename"].rpartition("/")
        if folder not in ("", "static") or not base.endswith(".ttf") or "VariableFont" in base:
            continue
        if base[:-4].rpartition("-")[0] == stem and _style_of(base) in dl["styles"]:
            picked.append(r)
    return picked


def _google_fonts(dl, tmp, notes):
    body = netutil.get_bytes("https://fonts.google.com/download/list?family=" + quote(dl["family"]))
    refs = google_pick(google_manifest(body), dl)
    out = []
    for r in refs:
        p = _write_member(r["filename"], netutil.get_bytes(r["url"]), tmp, notes)
        if p:
            out.append(p)
    return out


RECIPES = {"github_release": _github_release, "google_fonts": _google_fonts}


# ---------- install ----------

def user_font_dir():
    home = Path.home()
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local"))) / "Microsoft" / "Windows" / "Fonts"
    if sys.platform == "darwin":
        return home / "Library" / "Fonts"
    return home / ".local" / "share" / "fonts"


def _reg_name(family, style):
    """Registry value name: 'Pretendard (TrueType)' for Regular, 'Pretendard Bold (TrueType)' otherwise."""
    return f"{family} {style} (TrueType)".replace(" Regular (", " (")


def _norm_path(p):
    return os.path.normcase(os.path.abspath(str(p)))


def _register_windows(dst, family, style):
    """Register dst for the current user. The Fonts key may not exist (CreateKeyEx). Never overwrites a value that
    points to another file: raises FileExistsError instead."""
    import winreg
    key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows NT\CurrentVersion\Fonts", 0,
                             winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
    try:
        name = _reg_name(family, style)
        try:
            have = winreg.QueryValueEx(key, name)[0]
        except FileNotFoundError:
            have = None
        if have and _norm_path(have) != _norm_path(dst):
            raise FileExistsError(f"registry entry '{name}' already points to {have}")
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, str(dst))
    finally:
        winreg.CloseKey(key)


def _load_font(dst):
    """Best effort: load the font into the current session so running apps can see it."""
    try:
        import ctypes
        ctypes.windll.gdi32.AddFontResourceW(str(dst))
    except Exception:
        pass


def _broadcast_font_change():
    try:
        import ctypes
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001D, 0, 0, 0x0002, 1000, None)  # SMTO_ABORTIFHUNG
    except Exception:  # best effort
        pass


def _copy_atomic(src, dst):
    part = dst.with_name(dst.name + ".part")
    try:
        shutil.copyfile(src, part)
        os.replace(part, dst)
    finally:
        part.unlink(missing_ok=True)


def install_files(files, dest=None):
    """Copy .ttf files into dest (or the per-user font dir + registry on Windows). Returns (installed, present):
    lists of (family, style). Skips files that already exist with the same size, and (family, style) pairs that are
    installed elsewhere (real install only). Failures go to stderr."""
    real = dest is None
    target = Path(dest) if dest else user_font_dir()
    target.mkdir(parents=True, exist_ok=True)
    done, present = [], []
    for src in files:
        try:
            family, style = ImageFont.truetype(str(src), 12).getname()
        except (OSError, ValueError):
            _err(f"skipped {src.name} (not a readable TrueType font)")
            continue
        dst = target / src.name
        if real:
            have = dkfonts.installed_fonts().get(family, {}).get(style or "Regular")
            if have and _norm_path(have[0]) != _norm_path(dst):
                print(f"[fonts] {family} {style} already installed at {have[0]}")
                present.append((family, style))
                continue
        existed = dst.exists()
        copied = False
        try:
            if not (dst.exists() and dst.stat().st_size == src.stat().st_size):
                _copy_atomic(src, dst)
                copied = True
            if real and sys.platform == "win32":
                _register_windows(dst, family, style)
                _load_font(dst)
        except OSError as e:
            if copied and not existed:  # drop our unregistered copy, but never a file that was there before
                dst.unlink(missing_ok=True)
            _err(f"could not install {src.name}: {e}")
            continue
        done.append((family, style))
    if real and done:
        if sys.platform == "win32":
            _broadcast_font_change()
        elif sys.platform != "darwin" and shutil.which("fc-cache"):
            subprocess.run(["fc-cache", "-f", str(target)], check=False)
        getattr(dkfonts.installed_fonts, "cache_clear", lambda: None)()
    return done, present


def _all_styles_present(entry):
    """True if every style the recipe would install is already installed (entries without a style list: unknown)."""
    styles = entry["download"].get("styles")
    if not styles:
        return False

    have = next((v for k, v in dkfonts.installed_fonts().items() if dkfonts._norm(k) == dkfonts._norm(entry["family"])), {})
    return all(s in have for s in styles)


def cmd_install(entry_id, dest=None):
    entry = next((e for e in load_catalog() if e["id"] == entry_id), None)
    if entry is None:
        _err(f"unknown font id '{entry_id}' (see: python fonts.py catalog)")
        return 2
    dl = entry["download"]
    if dl["type"] == "manual":
        _err(f"{entry['family']} cannot be downloaded automatically. Get it from {entry['official_url']} "
             "- install manually, then restart PowerPoint.")
        return 1
    if dest is None and _all_styles_present(entry):
        print(f"[fonts] {entry['family']} is already installed (all wanted styles found).")
        return 0
    if dest is None and "WindowsApps" in sys.executable:
        _err("this Python comes from the Microsoft Store, which virtualizes registry and LocalAppData writes, so fonts "
             f"cannot be installed from here. Download {entry['family']} from {entry['official_url']}, install it manually "
             "(open the font file, then Install), and restart PowerPoint. Nothing was downloaded or installed.")
        return 1
    notes = []
    with tempfile.TemporaryDirectory(prefix="ppt-craft-fonts-") as tmp:
        try:
            files = RECIPES[dl["type"]](dl, tmp, notes)
        except netutil.RateLimited as e:
            limit = ("GitHub allows 60 unauthenticated API requests per hour" if dl["type"] == "github_release"
                     else "Google Fonts is limiting requests from this network")
            _err(f"{e}. {limit}; wait and retry, or install manually from {entry['official_url']}")
            return 1
        except (netutil.NetError, ValueError, KeyError) as e:
            _err(f"download failed for {entry['family']}: {e}")
            return 1
        for n in notes:
            _err(n)
        if not files:
            _err(f"no installable .ttf files found for {entry['family']} (recipe is outdated?). "
                 f"Install manually from {entry['official_url']}")
            return 1
        done, present = install_files(files, dest)
    if not done:
        if present:
            print(f"[fonts] {entry['family']}: every wanted style is already installed.")
            return 0
        _err(f"nothing was installed for {entry['family']}")
        return 1
    fams = {}
    for family, style in done:
        fams.setdefault(family, []).append(style)
    where = f"into {dest}" if dest else "for the current user"
    print(f"[fonts] installed {where}: " + "; ".join(f"{f} ({', '.join(s)})" for f, s in fams.items()))
    if entry.get("note"):
        print(f"[fonts] note: {entry['note']}")
    if not dest:
        print("[fonts] Restart PowerPoint to see new fonts.")
    return 0


# ---------- CLI ----------

def cmd_catalog(script=None, role=None, as_json=False):
    rows = []
    for e in load_catalog():
        if (script and script not in e["scripts"]) or (role and role not in e["roles"]):
            continue
        rows.append({**e, "installed": find_font_file(e["family"]) is not None})
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return
    for r in rows:
        state = "installed" if r["installed"] else ("manual" if r["download"]["type"] == "manual" else "available")
        print(f"{r['id']:<20} {r['family']:<20} {','.join(r['scripts']):<9} {','.join(r['roles']):<10} "
              f"{r['category']:<8} {state}")
        if r.get("note"):
            print(f"{'':<20} note: {r['note']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Installed fonts, free-font catalog, per-user install")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list")
    ls.add_argument("--hangul", action="store_true", help="only fonts that have Hangul glyphs")
    ls.add_argument("--grep", default="", help="partial match on the family name")
    cat = sub.add_parser("catalog", help="curated free fonts, with installed: true/false")
    cat.add_argument("--script", choices=["ko", "latin"])
    cat.add_argument("--role", choices=["head", "body", "mono"])
    cat.add_argument("--json", action="store_true")
    ins = sub.add_parser("install", help="download and install a catalog font for the current user")
    ins.add_argument("id")
    ins.add_argument("--dest", help="copy into this directory only (no registry); for tests")
    args = ap.parse_args(argv)
    if args.cmd == "catalog":
        cmd_catalog(args.script, args.role, args.json)
        return 0
    if args.cmd == "install":
        return cmd_install(args.id, args.dest)
    rows = []
    for family, styles in sorted(installed_fonts().items()):
        if args.grep.lower() not in family.lower():
            continue
        if args.hangul:
            try:
                if not has_hangul(find_font_file(family)):
                    continue
            except OSError:
                continue
        rows.append({"family": family, "styles": sorted(styles)})
    print(json.dumps(rows, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    sys.exit(main())
