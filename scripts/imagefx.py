"""Photo treatments and generated textures for ppt-craft.
Usage:
  python imagefx.py treat <image...> --mode harmonize|gray|duotone|tone --style style.json --out <W>/assets/treated
  python imagefx.py texture --kind paper|grain|dots|grid --opacity 0.06 --style style.json --out <W>/assets/texture-paper.png
  python imagefx.py compare <photo> --style style.json --out <W>/candidates/imagery [--focus x0 y0 x1 y1]
treat writes <stem>-<mode>.jpg (.png when the image has alpha) into --out and never touches the source.
duotone uses the style's ink (dark) and bg (light); if they are too close it falls back to gray.
texture needs a .png --out; --kind/--opacity default to the style's imagery.texture; the size follows the canvas ratio.
compare builds compare.pptx (4 treatments none/harmonize/gray/duotone as bleed-panel slides, then the patterns
bleed-panel/bleed-scrim/split), renders it and writes compare.png (rows "treat" and "pattern"), then prints its path.
It ignores imagery.patterns (it is what the user chooses them from).
Exit codes: 0 ok, 1 processing error, 2 usage error (compare: also no renderer)."""
import argparse
import math
import os
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from deckkit import Deck  # noqa: E402
from deckkit.legibility import AA_BODY, contrast, hex_rgb, rel_luminance  # noqa: E402
from deckkit.style import PATTERNS, TEXTURES, load_style  # noqa: E402

MODES = ("harmonize", "gray", "duotone", "tone")
MAX_TEXTURE_OPACITY = 0.1


def harmonize(im):
    return ImageEnhance.Color(im.convert("RGB")).enhance(0.92)


def gray(im):
    return ImageOps.grayscale(im).convert("RGB")


def duotone(im, dark_hex, light_hex):
    """Shadows get the darker of the two colors, highlights the lighter (so dark themes, where ink is light, still work)."""
    dark_hex, light_hex = sorted((dark_hex, light_hex), key=lambda h: rel_luminance(hex_rgb(h)))
    return ImageOps.colorize(ImageOps.grayscale(im), dark_hex, light_hex)


def tone(im):
    """Darker and quieter, for photos used as slide backgrounds."""
    return ImageEnhance.Color(ImageEnhance.Brightness(im.convert("RGB")).enhance(0.85)).enhance(0.7)


def texture(kind, color_hex, opacity, size=(1920, 1080), seed=7):
    """RGBA texture in one color; alpha never exceeds round(opacity * 255). Deterministic for a seed."""
    if kind not in TEXTURES:
        raise ValueError(f"texture kind must be one of {TEXTURES}")
    if not (0 < opacity <= MAX_TEXTURE_OPACITY):
        raise ValueError(f"texture opacity must be > 0 and <= {MAX_TEXTURE_OPACITY}")
    w, h = size
    cap = round(opacity * 255)
    rng = random.Random(seed)
    if kind in ("paper", "grain"):
        sw, sh = (max(1, w // 8), max(1, h // 8)) if kind == "paper" else (w, h)
        noise = Image.frombytes("L", (sw, sh), rng.randbytes(sw * sh))
        if kind == "paper":
            noise = noise.resize((w, h), Image.BICUBIC)
        alpha = noise.point(lambda v: round(v * opacity))
    else:
        alpha = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(alpha)
        if kind == "dots":
            for y in range(12, h, 24):
                for x in range(12, w, 24):
                    d.ellipse((x - 1.5, y - 1.5, x + 1.5, y + 1.5), fill=cap)
        else:
            for x in range(0, w, 48):
                d.line((x, 0, x, h), fill=cap, width=1)
            for y in range(0, h, 48):
                d.line((0, y, w, y), fill=cap, width=1)
    out = Image.new("RGBA", (w, h), hex_rgb(color_hex) + (0,))
    out.putalpha(alpha)
    return out


def _warn(msg):
    print(f"[imagefx] warning: {msg}", file=sys.stderr)


DUOTONE_WARNING = "duotone colors too close; using gray"
_RGB_PROFILE_MODES = ("RGB", "RGBA", "P")  # an ICC profile from another color space would be wrong on the RGB output


def _duotone_too_close(style):
    return contrast(hex_rgb(style["color"]["ink"]), hex_rgb(style["color"]["bg"])) < AA_BODY


def treat_file(src, mode, style, out_dir, warn=True):
    """Write <stem>-<mode>.jpg (or .png if the image has alpha) into out_dir and return its path.
    warn=False suppresses the duotone fallback warning (main prints it once per run)."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    src, out_dir = Path(src), Path(out_dir)
    ink, bg = style["color"]["ink"], style["color"]["bg"]
    if mode == "duotone" and _duotone_too_close(style):
        if warn:
            _warn(DUOTONE_WARNING)
        fx = gray
    else:
        fx = {"harmonize": harmonize, "gray": gray, "tone": tone, "duotone": lambda im: duotone(im, ink, bg)}[mode]
    with Image.open(src) as raw:
        icc = raw.info.get("icc_profile") if raw.mode in _RGB_PROFILE_MODES and mode != "duotone" else None
        im = ImageOps.exif_transpose(raw)
        im.load()
    has_alpha = im.has_transparency_data if hasattr(im, "has_transparency_data") else "transparency" in im.info
    if has_alpha or im.mode in ("RGBA", "LA", "PA"):
        im = im.convert("RGBA")
        alpha = im.getchannel("A")
        if alpha.getextrema()[0] == 255:  # fully opaque: the alpha channel carries nothing
            alpha = None
    else:
        alpha = None
    res = fx(im.convert("RGB"))
    out_dir.mkdir(parents=True, exist_ok=True)
    if alpha is not None:
        res.putalpha(alpha)
        dst = out_dir / f"{src.stem}-{mode}.png"
    else:
        dst = out_dir / f"{src.stem}-{mode}.jpg"
    if dst.exists() and dst.resolve() == src.resolve():
        raise ValueError(f"output {dst} would overwrite the source")
    if alpha is not None:
        res.save(dst, icc_profile=icc)
    else:
        res.save(dst, quality=90, icc_profile=icc)
    return dst


COMPARE_TREATMENTS = ("none", "harmonize", "gray", "duotone")
COMPARE_PATTERNS = ("bleed-panel", "bleed-scrim", "split")
COMPARE_BODY = "Body text sits on this side"


def compare(photo, style, out_dir, focus=None):
    """Build, render and sheet the imagery comparison. Returns the compare.png path.
    Raises render.RendererMissing when no renderer is available."""
    import render  # looked up at call time so tests can replace render.render
    from sheet import make_sheet

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    st = {**style, "imagery": {**style["imagery"], "patterns": list(PATTERNS), "max_bleed": 20}}
    d = Deck(st, lang="en")
    for mode in COMPARE_TREATMENTS:
        path = photo if mode == "none" else treat_file(photo, mode, st, out_dir / "treated")
        d.pattern("bleed-panel", mode, path, focus=focus)
    for name in COMPARE_PATTERNS:
        slide, box = d.pattern(name, name, photo, focus=focus, words=len(COMPARE_BODY.split()))
        if box:
            d.text(slide, box, COMPARE_BODY, "body", color=d.text_color)
    pptx = d.save(out_dir / "compare.pptx")
    slides = render.render(pptx, out_dir / "renders", width=960)["slides"]
    n = len(COMPARE_TREATMENTS)
    return make_sheet([slides[:n], slides[n:]], out_dir / "compare.png", labels=["treat", "pattern"])


def _key(path):
    return os.path.normcase(str(Path(path).resolve()))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Photo treatments and generated textures")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("treat")
    t.add_argument("images", nargs="+")
    t.add_argument("--mode", required=True, choices=MODES)
    t.add_argument("--style", required=True)
    t.add_argument("--out", required=True)
    x = sub.add_parser("texture")
    x.add_argument("--kind", choices=TEXTURES)
    x.add_argument("--opacity", type=float)
    x.add_argument("--style", required=True)
    x.add_argument("--out", required=True)
    c = sub.add_parser("compare")
    c.add_argument("photo")
    c.add_argument("--style", required=True)
    c.add_argument("--out", required=True)
    c.add_argument("--focus", nargs=4, type=float, metavar=("X0", "Y0", "X1", "Y1"))
    a = ap.parse_args(argv)  # argparse exits with 2 on usage errors
    try:
        style = load_style(a.style)
    except (OSError, ValueError) as e:
        print(f"[imagefx] bad style: {e}", file=sys.stderr)
        return 2
    if a.cmd == "texture":
        return _texture_cmd(a, style)
    if a.cmd == "compare":
        return _compare_cmd(a, style)
    if a.mode == "duotone" and _duotone_too_close(style):
        _warn(DUOTONE_WARNING)
    out_dir = Path(a.out)
    inputs = {_key(p) for p in a.images}
    written = {}  # output stem key -> path of the file written for it
    failed = 0
    for src in a.images:
        stem_key = _key(out_dir / f"{Path(src).stem}-{a.mode}")
        planned = [_key(out_dir / f"{Path(src).stem}-{a.mode}{ext}") for ext in (".jpg", ".png")]
        if stem_key in written:
            print(f"[imagefx] skip {src}: output name collides with {written[stem_key]}", file=sys.stderr)
            failed += 1
            continue
        if any(k in inputs for k in planned):
            print(f"[imagefx] skip {src}: output would overwrite an input file", file=sys.stderr)
            failed += 1
            continue
        try:
            dst = treat_file(src, a.mode, style, out_dir, warn=False)
        except Exception as e:  # one broken file must not block the rest
            print(f"[imagefx] skipped: {src}: {e}", file=sys.stderr)
            failed += 1
            continue
        written[stem_key] = dst
        print(dst)
    return 1 if failed else 0


def _compare_cmd(a, style):
    import render
    try:
        print(compare(a.photo, style, a.out, focus=a.focus))
    except render.RendererMissing:
        print(render.INSTALL_HELP, file=sys.stderr)
        return 2
    except Exception as e:  # render failures, a broken photo, a locked output file
        print(f"[imagefx] compare failed: {e}", file=sys.stderr)
        return 1
    return 0


def _texture_cmd(a, style):
    cfg = style["imagery"].get("texture") or {}
    kind = a.kind or cfg.get("kind")
    opacity = a.opacity if a.opacity is not None else cfg.get("opacity", 0.06)
    out = Path(a.out)
    if kind is None:
        print("[imagefx] texture needs --kind (the style has no imagery.texture)", file=sys.stderr)
        return 2
    if out.suffix.lower() != ".png":
        print("[imagefx] texture --out must be a .png file (the texture has alpha)", file=sys.stderr)
        return 2
    w, h = style["canvas"]["size"]
    try:
        px = max(1920, math.ceil(w * 150))  # deckkit warns under 150dpi across the slide width
        tex = texture(kind, style["color"]["ink"], opacity, size=(px, round(px * h / w)))
    except ValueError as e:
        print(f"[imagefx] {e}", file=sys.stderr)
        return 2
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        tex.save(out)
    except OSError as e:
        print(f"[imagefx] error: {e}", file=sys.stderr)
        return 1
    print(out)
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    sys.exit(main())
