"""Prepare user images: apply EXIF rotation, cap the long edge at 3000px, detect screenshot margins.
Usage: python images.py <images...> --out <decks/slug/assets>
Result: adds entries to assets/images.json (keeping type/focus/must_keep/note of existing entries) and prints the JSON.
Original files are never modified. Claude fills type/focus/must_keep/note by looking at the image."""
import argparse
import io
import json
import os
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageCms, ImageOps

MAX_EDGE = 3000
MAX_DOWNLOAD_PIXELS = 100_000_000  # a downloaded image above 100 MP is refused before it is decoded
BIG_PIXELS = 2_000_000  # above this (2 MP) a downloaded image without alpha is saved as JPEG even if it has few colors
# These are the user's own files, so raise the default limit (about 180M pixels). Remote downloads (assets.py) are only capped by
# bytes (50 MB full images, 3 MB thumbnails), which does not bound the decoded size: a small file can still expand to this many pixels.
Image.MAX_IMAGE_PIXELS = 400_000_000


def looks_flat(im):
    """Few distinct colors suggests a screenshot or diagram (Claude makes the final call by looking at the image)."""
    colors = im.convert("RGB").resize((128, 128)).getcolors(128 * 128)
    return len(colors) < 2500


def content_bbox(im, tol=12):
    """Content area [x0, y0, x1, y1] (0-1) minus solid-color border margins. The whole image if there is no margin."""
    rgb = im.convert("RGB")
    bg = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
    # Keep only values above tol per channel, then getbbox: if any channel differs from the background it counts as content.
    box = ImageChops.difference(rgb, bg).point(lambda v: 255 if v > tol else 0).getbbox()
    if not box:
        return [0.0, 0.0, 1.0, 1.0]
    w, h = rgb.size
    return [round(box[0] / w, 4), round(box[1] / h, 4), round(box[2] / w, 4), round(box[3] / h, 4)]


def _normalize_mode(im):
    """Convert to a mode that is safe to save and analyze (L/LA/P/RGB/RGBA). 16-bit becomes 8-bit L, CMYK etc. become RGB(A).
    The original ICC profile is not kept on a converted result (a profile from another color space would give wrong colors)."""
    if im.mode in ("1", "L", "LA", "P", "RGB", "RGBA"):
        return im
    icc = im.info.get("icc_profile")
    if im.mode == "I" or im.mode.startswith("I;16"):
        arr = im.convert("I")
        lo, hi = arr.getextrema()
        scale = 255.0 / (hi - lo) if hi > lo else 1.0
        out = arr.point(lambda v: (v - lo) * scale).convert("L")
    else:
        out = None
        if im.mode == "CMYK" and icc:  # if there is a profile, convert colors to sRGB
            try:
                out = ImageCms.profileToProfile(im, io.BytesIO(icc), ImageCms.createProfile("sRGB"),
                                                outputMode="RGB")
            except Exception:  # noqa: BLE001 - a broken profile falls back to a plain conversion
                out = None
        if out is None:
            out = im.convert("RGBA" if "A" in im.getbands() else "RGB")
    out.info.pop("icc_profile", None)
    return out


def prep(src, out_dir, name=None, downloaded=False):
    """name: output file name (without extension). Defaults to the source stem.
    downloaded=True (assets.py: images fetched from the web): a big image without alpha is always saved as JPEG.
    The user's own images keep the color-count rule, so screenshots stay lossless PNG."""
    src, out_dir = Path(src), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as raw:
        if downloaded and raw.width * raw.height > MAX_DOWNLOAD_PIXELS:  # header size only: nothing is decoded yet
            raise ValueError(f"image is {raw.width}x{raw.height} ({raw.width * raw.height // 1_000_000} MP), over the "
                             f"{MAX_DOWNLOAD_PIXELS // 1_000_000} MP limit for downloaded images")
        raw.draft("RGB", (MAX_EDGE, MAX_EDGE))  # JPEG only: decode big photos at a reduced size
        im = ImageOps.exif_transpose(raw)
        im.load()
    im = _normalize_mode(im)
    if im.mode in ("RGBA", "LA") and im.getchannel("A").getextrema()[0] == 255:  # fully opaque: the alpha channel carries nothing
        im = im.convert(im.mode[:-1])
    if max(im.size) > MAX_EDGE:
        im.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
    kind = "screenshot" if looks_flat(im) else "photo"
    alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
    # JPEG for anything without alpha that looks like a photo. A downloaded photo can have few colors and be misjudged as flat (as PNG
    # it bloats the deck), so downloads above BIG_PIXELS are JPEG too. The user's screenshots/diagrams stay lossless PNG.
    big = downloaded and im.width * im.height > BIG_PIXELS
    ext = ".jpg" if not alpha and (kind == "photo" or big) else ".png"
    stem = name or src.stem
    dst = out_dir / f"{stem}{ext}"
    if dst.resolve() == src.resolve():
        dst = out_dir / f"{stem}-prep{ext}"
    if ext == ".jpg":
        im.convert("RGB").save(dst, quality=90, icc_profile=im.info.get("icc_profile"))
    else:
        im.save(dst)
    return {"file": dst.name, "source": str(src.resolve()), "size": list(im.size),
            "kind_guess": kind, "content_bbox": content_bbox(im)}


def _unique_name(src, index):
    """If a different source with the same stem is already registered, use stem-2, stem-3, ..."""
    src = Path(src)
    resolved = str(src.resolve())
    n = 1
    while True:
        stem = src.stem if n == 1 else f"{src.stem}-{n}"
        owners = [e.get("source") for f, e in index.items() if Path(f).stem == stem]
        if not owners or resolved in owners:
            return stem
        n += 1


def load_index(out):
    path = Path(out) / "images.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json_atomic(path, obj):
    """Write JSON to a temp file in the same folder, then os.replace: a crash or a concurrent reader never sees a half-written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save_index(out, index):
    write_json_atomic(Path(out) / "images.json", index)


def merge_entry(index, info):
    """Add/refresh an images.json entry from prep() info, keeping an existing entry's type/focus/must_keep/note."""
    entry = index.get(info["file"], {"type": None, "focus": None, "must_keep": None, "note": ""})
    entry.update(info)
    index[info["file"]] = entry


def main(argv=None):
    ap = argparse.ArgumentParser(description="Prepare user images")
    ap.add_argument("images", nargs="+")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    index_path = out / "images.json"
    index = load_index(out)
    failed = 0
    for src in a.images:
        try:
            info = prep(src, out, _unique_name(src, index))
        except Exception as e:  # one broken file must not block the rest
            print(f"[images] skipped: {src}: {e}", file=sys.stderr)
            failed += 1
            continue
        merge_entry(index, info)
    if index or index_path.exists():
        save_index(out, index)
    print(json.dumps(index, ensure_ascii=False, indent=1))
    return 1 if failed else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    sys.exit(main())
