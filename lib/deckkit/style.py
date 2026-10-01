"""style.json loading and validation. Shared by deckkit and the scripts."""
import copy
import json
import re
from pathlib import Path

RATIOS = {"16:9": (40 / 3, 7.5), "4:3": (10.0, 7.5)}
ROLES = ("head", "title", "governing", "body", "caption", "mono")
COVERS = ("type", "band", "image")
STRUCTURES = ("assertion", "governing")
LAYOUTS = ("split", "statement", "figure")
PATTERNS = ("bleed-panel", "bleed-scrim", "split", "inset", "strip", "gallery", "figure", "annotated", "type-only")
TREATMENTS = ("none", "gray", "duotone")
TEXTURES = ("paper", "grain", "dots", "grid")
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")

DEFAULTS = {
    "canvas": {"ratio": "16:9", "margin": 0.6},
    "scale": {"head": 44, "title": 28, "governing": 20, "body": 18, "caption": 12, "mono": 14},
    "rhythm": {"line_height": 1.35, "tracking_head": -0.03, "tracking_body": -0.015},
    "cover": "type",
    "structure": "assertion",
    "layout": "split",
    "motifs": [],
    "avoid": [],
    "imagery": {"patterns": list(PATTERNS), "treatment": "none", "harmonize": True, "texture": None, "max_bleed": 3},
}


def load_style(src):
    """Take a path (str/Path) or a dict, fill in defaults, and return a new validated dict."""
    raw = copy.deepcopy(src) if isinstance(src, dict) else json.loads(Path(src).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("style.json: the top level must be an object")
    st = copy.deepcopy(DEFAULTS)
    for key, val in raw.items():
        if isinstance(val, dict) and isinstance(st.get(key), dict):
            st[key].update(val)
        else:
            st[key] = val
    _validate(st)
    w, h = RATIOS[st["canvas"]["ratio"]]
    m = st["canvas"]["margin"]
    st["canvas"]["size"] = (w, h)
    st["canvas"].setdefault("title_box", [m, 0.4, round(w - 2 * m, 3), 1.1])
    st["font"].setdefault("mono", st["font"]["body"])
    return st


def _validate(st):
    def fail(msg):
        raise ValueError(f"style.json: {msg}")

    def is_num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    for sec in ("canvas", "scale", "rhythm", "color", "font"):
        if sec in st and not isinstance(st[sec], dict):
            fail(f"{sec} must be an object")
    if not is_num(st["canvas"].get("margin")):
        fail("canvas.margin must be a number")
    for key, val in st["rhythm"].items():
        if not is_num(val):
            fail(f"rhythm.{key} must be a number")
    box = st["canvas"].get("title_box")
    if box is not None and not (isinstance(box, (list, tuple)) and len(box) == 4 and all(is_num(v) for v in box)):
        fail("canvas.title_box must be 4 numbers")

    color = st.get("color")
    if not isinstance(color, dict):
        fail("the color section is missing")
    for key in ("bg", "ink", "muted", "accent"):
        if not _HEX.match(str(color.get(key, ""))):
            fail(f"color.{key} must be in #RRGGBB format (got: {color.get(key)!r})")
    font = st.get("font")
    if not isinstance(font, dict):
        fail("the font section is missing")
    for key in ("head", "body"):
        if not str(font.get(key, "")).strip():
            fail(f"font.{key} is empty")
    if st["canvas"]["ratio"] not in RATIOS:
        fail(f"canvas.ratio must be one of {list(RATIOS)}")
    for role in ROLES:
        if not is_num(st["scale"].get(role)):
            fail(f"scale.{role} must be a number")
    if st["cover"] not in COVERS:
        fail(f"cover must be one of {COVERS}")
    if st["structure"] not in STRUCTURES:
        fail(f"structure must be one of {STRUCTURES}")
    if st["layout"] not in LAYOUTS:
        fail(f"layout must be one of {LAYOUTS}")
    _validate_imagery(st["imagery"], fail, is_num)


def _validate_imagery(im, fail, is_num):
    if not isinstance(im, dict):
        fail("imagery must be an object")
    extra = set(im) - {"patterns", "treatment", "harmonize", "max_bleed", "texture"}
    if extra:
        fail(f"imagery has unknown keys: {sorted(extra)}")
    pats = im.get("patterns")
    if not (isinstance(pats, list) and pats and all(p in PATTERNS for p in pats)):
        fail(f"imagery.patterns must be a non-empty list of {PATTERNS} (got: {pats!r})")
    if im.get("treatment") not in TREATMENTS:
        fail(f"imagery.treatment must be one of {TREATMENTS}")
    if not isinstance(im.get("harmonize"), bool):
        fail("imagery.harmonize must be true or false")
    mb = im.get("max_bleed")
    if not (isinstance(mb, int) and not isinstance(mb, bool) and 0 <= mb <= 20):
        fail("imagery.max_bleed must be an integer from 0 to 20")
    tex = im.get("texture")
    if tex is not None and not (isinstance(tex, dict) and tex.get("kind") in TEXTURES
                                and is_num(tex.get("opacity")) and 0 < tex["opacity"] <= 0.1):
        fail(f"imagery.texture must be null or {{kind: one of {TEXTURES}, opacity: >0 and <=0.1}}")
