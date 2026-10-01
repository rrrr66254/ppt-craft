"""Installed-font lookup. Matches by the family name in the font file's name table."""
import os
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_EXTS = {".ttf", ".otf", ".ttc"}
_REGULAR = ("Regular", "Normal", "Roman", "Book", "R")


def font_dirs():
    home = Path.home()
    if sys.platform == "win32":
        return [
            Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
            Path(os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local"))) / "Microsoft" / "Windows" / "Fonts",
        ]
    if sys.platform == "darwin":
        return [Path("/System/Library/Fonts"), Path("/Library/Fonts"), home / "Library" / "Fonts"]
    return [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), home / ".local" / "share" / "fonts", home / ".fonts"]


@lru_cache(maxsize=1)
def installed_fonts():
    """{family: {style: (path, index)}}. Reads every face of a .ttc. Scans only once per process."""
    found = {}
    for d in font_dirs():
        if not d.is_dir():
            continue
        for p in d.rglob("*"):
            ext = p.suffix.lower()
            if ext not in _EXTS:
                continue
            index = 0
            while True:
                try:
                    family, style = ImageFont.truetype(str(p), 12, index=index).getname()
                except (OSError, ValueError):
                    break
                if family:
                    found.setdefault(family, {}).setdefault(style or "Regular", (str(p), index))
                index += 1
                if ext != ".ttc":
                    break
    return found


def _norm(name):
    return name.lower().replace(" ", "").replace("-", "")


def find_font_file(family, bold=False):
    """Find the font ref (path, index) by family name. None if not found."""
    fonts = installed_fonts()
    styles = fonts.get(family) or next((v for k, v in fonts.items() if _norm(k) == _norm(family)), None)
    if not styles:
        return None
    if bold and "Bold" in styles:
        return styles["Bold"]
    return next((styles[s] for s in _REGULAR if s in styles), None) or next(iter(styles.values()))


def has_hangul(ref):
    """ref=(path, index). If the '한' glyph is drawn differently from the missing-glyph box (.notdef), the font counts as supporting Hangul."""
    path, index = ref
    font = ImageFont.truetype(path, 24, index=index)

    def glyph(ch):
        im = Image.new("L", (48, 48))
        ImageDraw.Draw(im).text((8, 8), ch, font=font, fill=255)
        return im.tobytes()

    return glyph("한") != glyph("\U000F0000")
