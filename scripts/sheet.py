"""Thumbnail comparison image (contact sheet).
Usage: python sheet.py --rows <folder1> [<folder2> ...] [--labels A B C] --out cmp.png
The slide-*.png files of each folder become one row."""
import argparse
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def slide_pngs(folder):
    """Return the folder's slide-N.png files sorted by number (numerically)."""
    found = []
    for p in Path(folder).glob("slide-*.png"):
        m = re.fullmatch(r"slide-(\d+)\.png", p.name)
        if m:
            found.append((int(m.group(1)), p))
    return [p for _, p in sorted(found)]


def make_sheet(rows, out, labels=None, thumb_w=480, gap=16, numbered=False):
    """rows: list of lists of image paths (one list = one row). labels: short label for the left of each row."""
    pairs = [(row, labels[i] if labels and i < len(labels) else "") for i, row in enumerate(rows) if row]
    if not pairs:
        raise ValueError("no images")
    rows = [[_thumb(p, thumb_w) for p in row] for row, _ in pairs]
    labels = [lab for _, lab in pairs] if labels else None
    thumb_h = max(im.height for row in rows for im in row)
    label_w = 56 if labels else 0
    ncols = max(len(r) for r in rows)
    sheet = Image.new("RGB", (label_w + gap + ncols * (thumb_w + gap), gap + len(rows) * (thumb_h + gap)),
                      (232, 232, 232))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=22)
    n = 1
    for r, row in enumerate(rows):
        y = gap + r * (thumb_h + gap)
        if labels:
            draw.text((16, y + thumb_h // 2 - 12), str(labels[r]), fill=(20, 20, 20), font=font)
        for c, thumb in enumerate(row):
            x = label_w + gap + c * (thumb_w + gap)
            sheet.paste(thumb, (x, y))
            draw.rectangle([x - 1, y - 1, x + thumb_w, y + thumb.height], outline=(170, 170, 170))
            if numbered:
                draw.rectangle([x, y, x + 34, y + 26], fill=(20, 20, 20))
                draw.text((x + 6, y + 2), str(n), fill=(255, 255, 255), font=font)
                n += 1
    out = Path(out)
    sheet.save(out)
    return out


def _thumb(path, thumb_w):
    with Image.open(path) as im:
        im = im.convert("RGB")
        return im.resize((thumb_w, round(im.height * thumb_w / im.width)), Image.LANCZOS)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Contact sheet")
    ap.add_argument("--rows", nargs="+", required=True, help="folders that contain slide-*.png")
    ap.add_argument("--labels", nargs="*")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    rows = [slide_pngs(d) for d in a.rows]
    print(make_sheet(rows, a.out, labels=a.labels))


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    main()
