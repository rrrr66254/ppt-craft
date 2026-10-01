"""Image placement patterns. Each helper creates the slide and returns (slide, content_box).

content_box is where the caller writes body text (None when the pattern leaves no room). Rules:
- A pattern missing from style.imagery.patterns raises ValueError. Text goes opposite the image focus.
- All x positions come from Deck.col(). Image shapes are named pc:<pattern>, panels and scrims pc:panel / pc:scrim.
- d.text_color is set to the color name ("ink" or "bg") for body text on the slide just built.

bleed-panel   full-bleed photo + opaque grid-aligned panel holding the title (and body).
bleed-scrim   full-bleed photo + solid translucent scrim (alpha >= 0.35, planned from the pixels under the text);
              falls back to bleed-panel when contrast cannot be reached or there are > 15 words.
split         photo in its columns, text in the others (ratio = image:text columns, tall photo gets the narrow part).
inset         photo inside the margins with a required caption line (I13).
strip         full-width band, at most 40% of the slide height.
gallery       2-4 equal cells in one row, optional wider hero, optional captions.
"""
from PIL import Image, ImageOps

from . import legibility as L
from .crop import cover_crop

MAX_WORDS_ON_PHOTO = 15
_BODY_H = 1.2          # room reserved for a short body line over a bleed-scrim
MIN_SCRIM = 0.35      # spec 2: a scrim reads as intentional from 0.35 up; more alpha never lowers contrast
_PAD = 0.3             # scrim padding around the text box
_CAPTION_H = 0.35
_HERO_SPANS = {2: (8, 4), 3: (6, 3), 4: (6, 2)}  # gallery columns for (hero, other)


def _allow(d, name):
    allowed = d.style["imagery"]["patterns"]
    if name not in allowed:
        raise ValueError(f"pattern {name} is not allowed by style.imagery.patterns ({allowed})")


def _side(side, focus):
    """Text side. Default: opposite the focus (focus centre x < 0.5 -> right); left without focus."""
    if side is None:
        return "right" if focus and (focus[0] + focus[2]) / 2 < 0.5 else "left"
    if side not in ("left", "right"):
        raise ValueError(f"side must be 'left' or 'right' (got: {side!r})")
    return side


def _title_y(d):
    _, y, _, h = d.style["canvas"]["title_box"]
    return y, h


def _stack(d, slide, bottom_up):
    """Send shapes to the back so the final order (back to front) is the given order, ahead of the text."""
    for shape in reversed(bottom_up):
        d.send_to_back(slide, shape)


def _plan_text(d, path, region, focus, must_keep, size_pt):
    """legibility.plan for the title region over the placed picture (EXIF-normalized). None if it cannot be planned."""
    color = d.style["color"]
    with Image.open(path) as raw:
        im = ImageOps.exif_transpose(raw)
        crop = cover_crop(im.width, im.height, d.W, d.H, focus, must_keep)
        if crop is None:
            return None
        box_px = L.slide_box_to_image_px(region, (0, 0, d.W, d.H), im.size, crop)
        try:
            return L.plan(L.region_pixels(im, box_px), color["ink"], color["bg"], size_pt)
        except ValueError:
            return None


def _finish(d, slide, box, text_color="ink"):
    d.text_color = text_color
    return slide, box


def bleed_panel(d, title, path, *, focus=None, must_keep=None, side=None, cols=5):
    _allow(d, "bleed-panel")
    side = _side(side, focus)
    if not 2 <= cols <= 8:
        raise ValueError(f"cols must be from 2 to 8 (got: {cols})")
    start = 0 if side == "left" else 12 - cols
    x, w = d.col(start, cols)
    ty, th = _title_y(d)
    th *= 1.5  # a narrow panel wraps the title onto more lines
    s = d.slide(title, box=(x, ty, w, th))
    pic = d.background(s, path, focus=focus, must_keep=must_keep)
    if side == "left":
        edge = sum(d.col(cols, 1))                  # the panel reaches one column past the text
        panel_box = (0, 0, edge, d.H)
    else:
        edge = d.col(11 - cols, 1)[0]
        panel_box = (edge, 0, d.W - edge, d.H)
    panel = d._tag(d.rect(s, panel_box, "bg"), "panel")
    _stack(d, s, [pic, panel])
    top = ty + th + 0.3
    return _finish(d, s, (x, top, w, d.content_bottom - top))


def bleed_scrim(d, title, path, *, focus=None, must_keep=None, side=None, words=0):
    _allow(d, "bleed-scrim")
    side = _side(side, focus)
    x, w = d.col(0 if side == "left" else 5, 7)
    ty, th = _title_y(d)
    body = (x, d.content_top, w, _BODY_H) if words else None
    region = (x, ty, w, (body[1] + body[3] if body else ty + th) - ty)
    size = d.style["scale"]["body" if words else "title"]
    plan = _plan_text(d, path, region, focus, must_keep, size)
    if words > MAX_WORDS_ON_PHOTO:
        d._warn(f"{words} words over a photo is too much text; using bleed-panel.")
    elif plan is None or plan["panel"]:
        d._warn("Text over image fails contrast; using bleed-panel.")
    else:
        return _scrim_slide(d, title, path, plan, region, body, (x, ty, w, th), focus, must_keep)
    return bleed_panel(d, title, path, focus=focus, must_keep=must_keep, side=side)


def _scrim_slide(d, title, path, plan, region, body, title_box, focus, must_keep):
    x, ty, w, _ = title_box
    s = d.slide(title, box=title_box, color=plan["text"])
    pic = d.background(s, path, focus=focus, must_keep=must_keep)
    layers = [pic]
    if plan["alpha"]:
        sx, sy = max(0, x - _PAD), max(0, ty - _PAD)
        sbox = (sx, sy, min(d.W, x + w + _PAD) - sx, min(d.H, region[1] + region[3] + _PAD) - sy)
        layers.append(d.scrim(s, sbox, color="ink" if plan["text"] == "bg" else "bg", alpha=max(plan["alpha"], MIN_SCRIM)))
    _stack(d, s, layers)
    return _finish(d, s, body, plan["text"])


def split(d, title, path, *, focus=None, must_keep=None, side=None, ratio=(5, 7), fit="cover"):
    """ratio = (image columns, text columns), summing to 12. `side` is the text side."""
    _allow(d, "split")
    side = _side(side, focus)
    if len(ratio) != 2 or sum(ratio) != 12 or min(ratio) < 1:
        raise ValueError(f"ratio must be two column counts that sum to 12 (got: {ratio})")
    with Image.open(path) as im:
        tall = im.height > im.width
    img_cols, text_cols = sorted(ratio) if tall else ratio  # a tall photo goes to the narrow part
    img_start, text_start = (text_cols, 0) if side == "left" else (0, img_cols)
    top, bottom = d.content_top, d.content_bottom
    ix, iw = d.col(img_start, img_cols)
    tx, tw = d.col(text_start, text_cols)
    s = d.slide(title)
    d._tag(d.image(s, (ix, top, iw, bottom - top), path, fit=fit, focus=focus, must_keep=must_keep), "split")
    return _finish(d, s, (tx, top, tw, bottom - top))


def inset(d, title, path, *, caption, focus=None, fit="contain", span=8):
    _allow(d, "inset")
    if not (caption and str(caption).strip()):
        raise ValueError("inset needs a caption with provenance: source, date, place (I13)")
    if not 3 <= span <= 12:
        raise ValueError(f"span must be from 3 to 12 (got: {span})")
    x, w = d.col(0, span)
    top = d.content_top
    bottom = d.content_bottom - _CAPTION_H - 0.1
    s = d.slide(title)
    pic = d.image(s, (x, top, w, bottom - top), path, fit=fit, focus=focus)
    if fit == "contain":
        pic.left = round(x * 914400)  # keep the picture on the grid edge, caption aligned with it
    d._tag(pic, "inset")
    cy = (pic.top + pic.height) / 914400 + 0.1
    d.text(s, (x, cy, w, _CAPTION_H), caption, "caption", color="muted")
    if 12 - span < 3:
        return _finish(d, s, None)
    rx, rw = d.col(span, 12 - span)
    return _finish(d, s, (rx, top, rw, bottom - top))


def strip(d, title, path, *, focus=None, position="bottom", height_ratio=0.35):
    _allow(d, "strip")
    if not 0 < height_ratio <= 0.4:
        raise ValueError(f"height_ratio must be in (0, 0.4] (got: {height_ratio})")
    if position not in ("top", "bottom"):
        raise ValueError(f"position must be 'top' or 'bottom' (got: {position!r})")
    h = d.H * height_ratio
    ty, th = _title_y(d)
    if position == "bottom":
        s = d.slide(title)
        y, top, bottom = d.H - h, d.content_top, d.H - h - 0.3
    else:
        ty = h + 0.3
        s = d.slide(title, box=(d.m, ty, d.W - 2 * d.m, th))
        y, top, bottom = 0, ty + th + 0.3, d.content_bottom
    d._tag(d.image(s, (0, y, d.W, h), path, focus=focus), "strip")
    x, w = d.col(0, 12)
    return _finish(d, s, (x, top, w, bottom - top))


def gallery(d, title, paths, *, captions=None, hero=None):
    """2-4 images as N cells in one row (same crop ratio, same height). hero = index of the wider cell."""
    _allow(d, "gallery")
    paths = list(paths)
    n = len(paths)
    if not 2 <= n <= 4:
        raise ValueError(f"gallery takes 2 to 4 images (got: {n})")
    if hero is not None and not 0 <= hero < n:
        raise ValueError(f"hero must be an image index from 0 to {n - 1} (got: {hero})")
    if captions is not None and len(captions) != n:
        raise ValueError(f"captions must have one entry per image ({n}), got {len(captions)}")
    spans = [12 // n] * n
    if hero is not None:
        wide, narrow = _HERO_SPANS[n]
        spans = [wide if i == hero else narrow for i in range(n)]
    s = d.slide(title)
    top, avail = d.content_top, d.content_bottom - d.content_top - _CAPTION_H - 0.1
    h = min(avail, d.col(0, min(spans))[1] / 1.2)
    start = 0
    for i, (path, span) in enumerate(zip(paths, spans)):
        x, w = d.col(start, span)
        d._tag(d.image(s, (x, top, w, h), path), "gallery")
        if captions:
            d.text(s, (x, top + h + 0.1, w, _CAPTION_H), captions[i], "caption", color="muted")
        start += span
    if not captions:
        d._warn("Gallery without captions: add source/date/place for each image (I13).")
    return _finish(d, s, None)


HELPERS = {"bleed-panel": bleed_panel, "bleed-scrim": bleed_scrim, "split": split, "inset": inset,
           "strip": strip, "gallery": gallery}
