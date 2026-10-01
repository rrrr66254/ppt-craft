"""Photo treatments and generated textures for ppt-craft.
Usage:
  python imagefx.py treat <image...> --mode harmonize|gray|duotone|tone --style style.json --out <W>/assets/treated
  python imagefx.py texture --kind paper|grain|dots|grid --opacity 0.06 --style style.json --out <W>/assets/texture-paper.png
treat writes <stem>-<mode>.jpg (.png when the image has alpha) into --out and never touches the source.
duotone uses the style's ink (dark) and bg (light); if they are too close it falls back to gray.
Exit codes: 0 ok, 1 processing error, 2 usage error."""
import argparse
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from deckkit.legibility import AA_BODY, contrast, hex_rgb  # noqa: E402
from deckkit.style import TEXTURES, load_style  # noqa: E402

MODES = ("harmonize", "gray", "duotone", "tone")
MAX_TEXTURE_OPACITY = 0.1


def harmonize(im):
    return ImageEnhance.Color(im.convert("RGB")).enhance(0.92)


def gray(im):
    return ImageOps.grayscale(im).convert("RGB")


def duotone(im, dark_hex, light_hex):
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


def treat_file(src, mode, style, out_dir):
    """Write <stem>-<mode>.jpg (or .png if the image has alpha) into out_dir and return its path."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    src, out_dir = Path(src), Path(out_dir)
    ink, bg = style["color"]["ink"], style["color"]["bg"]
    if mode == "duotone" and contrast(hex_rgb(ink), hex_rgb(bg)) < AA_BODY:
        _warn("duotone colors too close; using gray")
        fx = gray
    else:
        fx = {"harmonize": harmonize, "gray": gray, "tone": tone, "duotone": lambda im: duotone(im, ink, bg)}[mode]
    with Image.open(src) as raw:
        im = ImageOps.exif_transpose(raw)
        im.load()
    alpha = im.getchannel("A") if "A" in im.getbands() else None
    res = fx(im.convert("RGB"))
    out_dir.mkdir(parents=True, exist_ok=True)
    if alpha is not None:
        res.putalpha(alpha)
        dst = out_dir / f"{src.stem}-{mode}.png"
        res.save(dst)
    else:
        dst = out_dir / f"{src.stem}-{mode}.jpg"
        res.save(dst, quality=90)
    return dst


def main(argv=None):
    ap = argparse.ArgumentParser(description="Photo treatments and generated textures")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("treat")
    t.add_argument("images", nargs="+")
    t.add_argument("--mode", required=True, choices=MODES)
    t.add_argument("--style", required=True)
    t.add_argument("--out", required=True)
    x = sub.add_parser("texture")
    x.add_argument("--kind", required=True, choices=TEXTURES)
    x.add_argument("--opacity", type=float, default=0.06)
    x.add_argument("--style", required=True)
    x.add_argument("--out", required=True)
    a = ap.parse_args(argv)  # argparse exits with 2 on usage errors
    try:
        style = load_style(a.style)
    except (OSError, ValueError) as e:
        print(f"[imagefx] bad style: {e}", file=sys.stderr)
        return 2
    if a.cmd == "texture":
        try:
            tex = texture(a.kind, style["color"]["ink"], a.opacity)
        except ValueError as e:
            print(f"[imagefx] {e}", file=sys.stderr)
            return 2
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        tex.save(out)
        print(out)
        return 0
    failed = 0
    for src in a.images:
        try:
            print(treat_file(src, a.mode, style, a.out))
        except Exception as e:  # one broken file must not block the rest
            print(f"[imagefx] skipped: {src}: {e}", file=sys.stderr)
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    sys.exit(main())
