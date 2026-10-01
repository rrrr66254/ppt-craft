"""Image placement patterns. Each helper creates the slide and returns (slide, content_box).

content_box is where the caller writes body text (None when the pattern leaves no room). Rules:
- A pattern missing from style.imagery.patterns raises ValueError. Text goes opposite the image focus.
- All x positions come from Deck.col(). Image shapes are named pc:<pattern> (backgrounds pc:bleed-panel / pc:bleed-scrim),
  panels and scrims pc:panel / pc:scrim.
- All helpers take focus / must_keep / words (ignored where it makes no difference). inset also requires caption.
- d.text_color is set to the color name ("ink" or "bg") for body text on the slide just built.

bleed-panel   full-bleed photo + opaque grid-aligned panel holding the title (and body).
bleed-scrim   full-bleed photo + solid translucent scrim (alpha >= 0.35, planned from the pixels under the text);
              falls back to bleed-panel when contrast cannot be reached or there are > 15 words.
suggest()     content-driven ranking of up to 2 patterns per slide (see its docstring).
split         photo half-bleed (full height, to the slide edge) in its columns, title and text in the others
              (ratio = image:text columns, tall photo gets the narrow part). fit="contain" keeps the picture inside
              the content area. d.footer keeps itself on the text side.
inset         photo inside the margins with a required caption line (I13).
strip         full-width band, at most 40% of the slide height.
gallery       2-4 equal cells in one row; with a hero, the others stack beside it to the same height; captions.
"""
from pathlib import Path

from PIL import Image
from pptx.util import Inches

from . import legibility as L
from . import textfit
from .crop import cover_crop
from .style import PATTERNS

MAX_WORDS_ON_PHOTO = 15
MAX_FOCUS_COVER = 0.25  # a bleed panel / text band may cover at most this share of the image focus
_BODY_H = 1.2          # room reserved for a short body line over a bleed-scrim
MIN_SCRIM = 0.35      # spec 2: a scrim reads as intentional from 0.35 up; more alpha never lowers contrast
_PAD = 0.3             # scrim padding around the text box
_CAPTION_H = 0.35


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


def _title_box(d, x, w, role, lines):
    """Title-row box at x, w. The "title" role keeps title_box's height (titles line up across slides); a bigger role
    (cover "head") gets a box tall enough for `lines` lines at its size, with the style's line spacing."""
    d._check(role=role)
    ty, th = _title_y(d)
    if role != "title":
        need = lines * 1.2 * d.style["scale"][role] * d.style["rhythm"]["line_height"] / textfit.SAFETY / 72
        th = max(th, need)
    return (x, ty, w, th)


def _stack(d, slide, bottom_up):
    """Send shapes to the back so the final order (back to front) is the given order, ahead of the text."""
    for shape in reversed(bottom_up):
        d.send_to_back(slide, shape)


def _plan_text(d, path, region, focus, must_keep, size_pt):
    """legibility.plan for the title region over the placed picture. PowerPoint draws the raw pixel orientation
    (EXIF is ignored), so the raw image is sampled. Returns (plan, problem); problem is None, "must_keep" or "unanalyzable"."""
    color = d.style["color"]
    with Image.open(path) as im:
        crop = cover_crop(im.width, im.height, d.W, d.H, focus, must_keep)
        if crop is None:
            return None, "must_keep"
        box_px = L.slide_box_to_image_px(region, (0, 0, d.W, d.H), im.size, crop)
        if im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info:
            # transparent pixels show the slide background, not black
            rgba = im.convert("RGBA")
            im = Image.new("RGB", rgba.size, L.hex_rgb(color["bg"]))
            im.paste(rgba, mask=rgba.getchannel("A"))
        try:
            return L.plan(L.region_pixels(im, box_px), color["ink"], color["bg"], size_pt), None
        except ValueError:
            return None, "unanalyzable"


def _per_image(value, n, name):
    """focus / must_keep for a gallery: None, one region for all images, or one entry (region or None) per image."""
    if value is None:
        return [None] * n
    if len(value) == 4 and all(isinstance(v, (int, float)) for v in value):
        return [value] * n
    if len(value) != n:
        raise ValueError(f"{name} must be one region or one entry per image ({n}), got {len(value)}")
    return list(value)


def _other(side):
    return "right" if side == "left" else "left"


def _focus_cover(d, path, focus, must_keep, box):
    """Share (0..1) of the visible image focus that `box` (x, y, w, h in slide inches) covers, mapping the focus
    through the actual cover crop. 0 without a focus (or when the crop cannot be made)."""
    if not focus:
        return 0.0
    with Image.open(path) as im:
        crop = cover_crop(im.width, im.height, d.W, d.H, focus, must_keep)
    if crop is None:
        return 0.0
    l, t, r, b = crop
    sx, sy = d.W / (1 - l - r), d.H / (1 - t - b)
    fx0, fx1 = ((focus[i] - l) * sx for i in (0, 2))
    fy0, fy1 = ((focus[i] - t) * sy for i in (1, 3))
    fx0, fx1, fy0, fy1 = max(fx0, 0), min(fx1, d.W), max(fy0, 0), min(fy1, d.H)
    area = max(fx1 - fx0, 0) * max(fy1 - fy0, 0)
    if area <= 0:
        return 0.0
    x, y, w, h = box
    overlap = max(min(fx1, x + w) - max(fx0, x), 0) * max(min(fy1, y + h) - max(fy0, y), 0)
    return overlap / area


def _warn_covers(d, path, what):
    d._warn(f"{Path(path).name}: the {what} covers the image focus; use split or pass a focus that sits clear of the text side.")


def _panel_box(d, side, cols):
    """The opaque panel: full height, from the text-side slide edge to one column past the text columns."""
    if side == "left":
        return (0, 0, sum(d.col(cols, 1)), d.H)
    edge = d.col(11 - cols, 1)[0]
    return (edge, 0, d.W - edge, d.H)


def _band_box(d, side):
    """The scrim band: full height, from the text-side slide edge to the 7 text columns' far edge plus padding."""
    x, w = d.col(0 if side == "left" else 5, 7)
    return (0, 0, x + w + _PAD, d.H) if side == "left" else (x - _PAD, 0, d.W - (x - _PAD), d.H)


def _finish(d, slide, box, text_color="ink"):
    d.text_color = text_color
    return slide, box


def bleed_panel(d, title, path, *, focus=None, must_keep=None, side=None, cols=5, words=0, role="title"):
    """words is accepted for interchangeability and ignored: the opaque panel always holds the text.
    role: title role (use "head" for a cover); the title box grows to fit 3 lines of it."""
    _allow(d, "bleed-panel")
    explicit = side is not None
    side = _side(side, focus)
    if not 2 <= cols <= 8:
        raise ValueError(f"cols must be from 2 to 8 (got: {cols})")
    side, cols = _clear_panel(d, path, focus, must_keep, side, cols, explicit)
    start = 0 if side == "left" else 12 - cols
    x, w = d.col(start, cols)
    _, ty, _, th = _title_box(d, x, w, role, 3)
    th = max(th, _title_y(d)[1] * 1.5)  # a narrow panel wraps the title onto more lines
    s = d.slide(title, box=(x, ty, w, th), role=role)
    pic = d.background(s, path, focus=focus, must_keep=must_keep, pattern="bleed-panel")
    panel = d._tag(d.rect(s, _panel_box(d, side, cols), "bg"), "panel")
    _stack(d, s, [pic, panel])
    top = ty + th + 0.3
    return _finish(d, s, (x, top, w, d.content_bottom - top))


def _clear_panel(d, path, focus, must_keep, side, cols, explicit):
    """(side, cols) whose panel covers at most MAX_FOCUS_COVER of the focus: first the other side (unless the caller
    passed side), then fewer columns down to 4. Otherwise warn and keep the request."""
    sides = [side] if explicit else [side, _other(side)]
    for c in range(cols, min(cols, 4) - 1, -1):
        for sd in sides:
            if _focus_cover(d, path, focus, must_keep, _panel_box(d, sd, c)) <= MAX_FOCUS_COVER:
                return sd, c
    _warn_covers(d, path, "panel")
    return side, cols


def bleed_scrim(d, title, path, *, focus=None, must_keep=None, side=None, words=0, role="title"):
    """role: title role (use "head" for a cover); legibility is planned at that size (at body size when words > 0)."""
    _allow(d, "bleed-scrim")
    explicit = side is not None
    side = _side(side, focus)
    for sd in [side] if explicit else [side, _other(side)]:
        if _focus_cover(d, path, focus, must_keep, _band_box(d, sd)) <= MAX_FOCUS_COVER:
            side = sd
            break
    else:
        _warn_covers(d, path, "text band")
    x, w = d.col(0 if side == "left" else 5, 7)
    _, ty, _, th = tbox = _title_box(d, x, w, role, 2)
    body = (x, ty + th + 0.3, w, _BODY_H) if words else None
    region = (x, ty, w, (body[1] + body[3] if body else ty + th) - ty)
    size = d.style["scale"]["body" if words else role]
    plan, problem = _plan_text(d, path, region, focus, must_keep, size)
    if words > MAX_WORDS_ON_PHOTO:
        d._warn(f"{words} words over a photo is too much text; using bleed-panel.")
    elif problem == "must_keep":
        d._warn(f"{Path(path).name}: the must_keep region cannot be kept at the full-bleed crop; using bleed-panel.")
    elif problem:
        d._warn("Text over image could not be analyzed; using bleed-panel.")
    elif plan["panel"]:
        d._warn("Text over image fails contrast; using bleed-panel.")
    else:
        return _scrim_slide(d, title, path, plan, body, tbox, focus, must_keep, side, role)
    return bleed_panel(d, title, path, focus=focus, must_keep=must_keep, side=side, role=role)


def _scrim_slide(d, title, path, plan, body, title_box, focus, must_keep, side, role):
    x, ty, w, _ = title_box
    s = d.slide(title, box=title_box, color=plan["text"], role=role)
    pic = d.background(s, path, focus=focus, must_keep=must_keep, pattern="bleed-scrim")
    layers = [pic]
    if plan["alpha"]:
        layers.append(d.scrim(s, _band_box(d, side), color="ink" if plan["text"] == "bg" else "bg", alpha=max(plan["alpha"], MIN_SCRIM)))
    _stack(d, s, layers)
    return _finish(d, s, body, plan["text"])


def split(d, title, path, *, focus=None, must_keep=None, side=None, ratio=(5, 7), fit="cover", words=0, role="title"):
    """ratio = (image columns, text columns), summing to 12. `side` is the text side. words is ignored.
    role: title role; the title box grows to fit 2 lines of it."""
    _allow(d, "split")
    side = _side(side, focus)
    if len(ratio) != 2 or sum(ratio) != 12 or min(ratio) < 1:
        raise ValueError(f"ratio must be two column counts that sum to 12 (got: {ratio})")
    with Image.open(path) as im:
        tall = im.height > im.width
    img_cols, text_cols = sorted(ratio) if tall else ratio  # a tall photo goes to the narrow part
    img_start, text_start = (text_cols, 0) if side == "left" else (0, img_cols)
    ix, iw = d.col(img_start, img_cols)
    tx, tw = d.col(text_start, text_cols)
    bottom = d.content_bottom
    if fit == "cover":  # half-bleed: full slide height, from the image columns' grid edge to the slide edge
        tbox = _title_box(d, tx, tw, role, 2)  # the title never runs under the photo
        top = tbox[1] + tbox[3] + 0.3
        box = (0, 0, ix + iw, d.H) if side == "right" else (ix, 0, d.W - ix, d.H)
    else:
        tbox = _title_box(d, d.m, d.W - 2 * d.m, role, 2)
        top = tbox[1] + tbox[3] + 0.3
        box = (ix, top, iw, bottom - top)
    s = d.slide(title, box=tbox, role=role)
    pic = d.image(s, box, path, fit=fit, focus=focus, must_keep=must_keep)
    if fit == "contain":  # a contained picture hugs the grid edge on its own side of the slide
        pic.left = Inches(ix + iw) - pic.width if side == "left" else Inches(ix)
    d._tag(pic, "split")
    return _finish(d, s, (tx, top, tw, bottom - top))


def inset(d, title, path, *, caption, focus=None, must_keep=None, fit="contain", span=8, words=0):
    """words is ignored: the free columns beside the picture are returned as the content box."""
    _allow(d, "inset")
    if not (caption and str(caption).strip()):
        raise ValueError("inset needs a caption with provenance: source, date, place (I13)")
    if not 3 <= span <= 12:
        raise ValueError(f"span must be from 3 to 12 (got: {span})")
    x, w = d.col(0, span)
    top = d.content_top
    bottom = d.content_bottom - _CAPTION_H - 0.1
    s = d.slide(title)
    pic = d.image(s, (x, top, w, bottom - top), path, fit=fit, focus=focus, must_keep=must_keep)
    d._tag(pic, "inset")
    cy = (pic.top + pic.height) / 914400 + 0.1
    d.text(s, (x, cy, w, _CAPTION_H), caption, "caption", color="muted")
    if 12 - span < 3:
        return _finish(d, s, None)
    rx, rw = d.col(span, 12 - span)
    return _finish(d, s, (rx, top, rw, bottom - top))


def strip(d, title, path, *, focus=None, must_keep=None, position="bottom", height_ratio=0.35, words=0):
    """words is ignored. A bottom band ends at content_bottom, above the footer zone."""
    _allow(d, "strip")
    if not 0 < height_ratio <= 0.4:
        raise ValueError(f"height_ratio must be in (0, 0.4] (got: {height_ratio})")
    if position not in ("top", "bottom"):
        raise ValueError(f"position must be 'top' or 'bottom' (got: {position!r})")
    h = d.H * height_ratio
    ty, th = _title_y(d)
    if position == "bottom":
        s = d.slide(title)
        y = d.content_bottom - h
        top, bottom = d.content_top, y - 0.3
    else:
        ty = h + 0.3
        s = d.slide(title, box=(d.m, ty, d.W - 2 * d.m, th))
        y, top, bottom = 0, ty + th + 0.3, d.content_bottom
    d._tag(d.image(s, (0, y, d.W, h), path, focus=focus, must_keep=must_keep), "strip")
    x, w = d.col(0, 12)
    return _finish(d, s, (x, top, w, bottom - top))


def _row_cells(d, n, avail):
    """Equal cells in one row, top-aligned: (x, y, w, h) image boxes sharing one crop ratio."""
    cells = [d.col(i * (12 // n), 12 // n) for i in range(n)]
    ratio = max(1.2, cells[0][1] / avail)
    return [(x, d.content_top, w, w / ratio) for x, w in cells]


def _hero_cells(d, n, hero, cap):
    """Hero (8 columns, full height) with the other images stacked in one 4-column column beside it, so both end at
    the same height. The hero sits on the left unless it is the last image. None if the stacked cells would be too
    wide or too narrow a crop (ratio outside 0.6..2.5)."""
    top, total, k, gap = d.content_top, d.content_bottom - d.content_top, n - 1, 0.25
    h_other = (total - (k - 1) * gap) / k - cap
    hero_left = hero != n - 1
    hx, hw = d.col(0 if hero_left else 4, 8)
    ox, ow = d.col(8 if hero_left else 0, 4)
    if h_other <= 0 or not 0.6 <= ow / h_other <= 2.5:
        return None
    cells = {hero: (hx, top, hw, total - cap)}
    for j, i in enumerate(i for i in range(n) if i != hero):
        cells[i] = (ox, top + j * (h_other + cap + gap), ow, h_other)
    return [cells[i] for i in range(n)]


def gallery(d, title, paths, *, captions=None, hero=None, focus=None, must_keep=None, words=0):
    """2-4 images. Without hero: N equal cells in one row (one crop ratio). With hero: that image is big (8 columns,
    full height) and the others are stacked beside it in one equal-cell column, so the slide has no empty quarter;
    the hero sits on the left unless it is the last image. If the stack would need a crop outside 0.6..2.5 (4 images
    with captions), it warns and uses the equal row. Captions go under each cell.
    focus / must_keep: one region for all images or a list with one entry per image. words is ignored."""
    _allow(d, "gallery")
    paths = list(paths)
    n = len(paths)
    if not 2 <= n <= 4:
        raise ValueError(f"gallery takes 2 to 4 images (got: {n})")
    if hero is not None and not 0 <= hero < n:
        raise ValueError(f"hero must be an image index from 0 to {n - 1} (got: {hero})")
    if captions is not None and len(captions) != n:
        raise ValueError(f"captions must have one entry per image ({n}), got {len(captions)}")
    focus, must_keep = _per_image(focus, n, "focus"), _per_image(must_keep, n, "must_keep")
    cap = _CAPTION_H + 0.1 if captions else 0.0
    cells = None
    if hero is not None:
        cells = _hero_cells(d, n, hero, cap)
        if cells is None:
            d._warn(f"Gallery hero with {n} images has no room to stack the others; using equal cells.")
    cells = cells or _row_cells(d, n, d.content_bottom - d.content_top - _CAPTION_H - 0.1)
    s = d.slide(title)
    for i, (path, (x, y, w, h)) in enumerate(zip(paths, cells)):
        d._tag(d.image(s, (x, y, w, h), path, focus=focus[i], must_keep=must_keep[i]), "gallery")
        if captions:
            d.text(s, (x, y + h + 0.1, w, _CAPTION_H), captions[i], "caption", color="muted")
    if not captions:
        d._warn("Gallery without captions: add source/date/place for each image (I13).")
    return _finish(d, s, None)


HELPERS = {"bleed-panel": bleed_panel, "bleed-scrim": bleed_scrim, "split": split, "inset": inset,
           "strip": strip, "gallery": gallery}


ROLES = ("cover", "section", "statement", "evidence", "comparison", "detail")


def suggest(image, role, words=0, n_images=None, prev=(), imagery=None, bleed_used=0):
    """Return up to 2 ranked {"pattern", "reason", "params"} for one slide.
    image: images.json entry (type, size [w, h], focus, must_keep) or None. prev: patterns of the previous 2 slides.
    type-only is always allowed. A pattern already used on both of the previous 2 slides is skipped."""
    imagery = imagery or {"patterns": list(PATTERNS), "max_bleed": 3}
    allowed = imagery["patterns"]
    n = n_images if n_images is not None else (1 if image else 0)
    out = []

    def add(p, reason, **params):
        if (p in allowed or p == "type-only") and p not in [o["pattern"] for o in out] and list(prev[-2:]) != [p, p]:
            out.append({"pattern": p, "reason": reason, "params": params})

    def result():
        return out[:2] or [{"pattern": "type-only", "reason": "fallback", "params": {}}]

    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}")
    if n == 0 or image is None:
        add("type-only", "no image that proves the point (H7/I8)")
        return result()
    kind = image.get("type") or image.get("kind_guess")
    w, h = (image.get("size") or [0, 0])[:2]
    aspect = (w / h) if w and h else 1.5
    fx = image.get("focus")
    side = "right" if fx and (fx[0] + fx[2]) / 2 < 0.5 else "left"
    if kind in ("diagram", "logo"):
        add("figure", f"{kind}: never cropped, captioned")
    if kind == "screenshot":
        add("annotated", "real screen as evidence (H3)")
        add("inset", "screenshot with caption")
    crops = kind not in ("diagram", "logo")  # split / gallery / strip cover-crop the picture
    if n >= 2 and crops:
        add("gallery", f"{n} comparable images")
    if aspect >= 3 and crops:
        add("strip", f"panoramic {aspect:.1f}:1")
    if role in ("cover", "section", "statement") and kind not in ("diagram", "logo", "screenshot"):
        if bleed_used < imagery.get("max_bleed", 3):
            if words > MAX_WORDS_ON_PHOTO:
                add("bleed-panel", f"{role} with {words} words: opaque panel", side=side)
            else:
                add("bleed-scrim", f"{role}, short text over the quiet side", side=side)
                add("bleed-panel", "fallback if contrast fails", side=side)
    if role in ("evidence", "detail", "comparison", "cover", "section", "statement"):
        if crops:
            add("split", "photo as evidence beside the claim", side=side, ratio=(5, 7) if aspect >= 1 else (4, 8))
        add("inset", "supporting photo with caption")
    add("type-only", "fallback")
    return result()
