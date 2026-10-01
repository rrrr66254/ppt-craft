"""Text-over-image legibility (WCAG 2.x). Pure functions over a PIL image."""
from PIL import Image

AA_BODY, AA_LARGE = 4.5, 3.0
MAX_SCRIM = 0.7
_STEP = 0.05


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rel_luminance(rgb):
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(rgb1, rgb2):
    a, b = sorted((rel_luminance(rgb1), rel_luminance(rgb2)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def region_pixels(img, box_px, max_side=64):
    """RGB pixels of box_px (x0, y0, x1, y1) in image pixels, downsampled (averages specks away)."""
    x0, y0, x1, y1 = (int(round(v)) for v in box_px)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(img.width, max(x0 + 1, x1)), min(img.height, max(y0 + 1, y1))
    reg = img.convert("RGB").crop((x0, y0, x1, y1))
    reg.thumbnail((max_side, max_side), Image.BOX)
    return list(getattr(reg, "get_flattened_data", reg.getdata)())  # getdata is deprecated in Pillow 12.1+


def _blend(c, s, a):
    return tuple(round(a * sv + (1 - a) * cv) for cv, sv in zip(c, s))


def _min_alpha(pixels, text_rgb, scrim_rgb, need):
    a = 0.0
    while a <= MAX_SCRIM + 1e-9:
        if min(contrast(text_rgb, _blend(p, scrim_rgb, a)) for p in pixels) >= need:
            return round(a, 2)
        a += _STEP
    return None


def plan(pixels, ink_hex, bg_hex, size_pt):
    """Choose text color and scrim for text over these pixels.
    Returns {"text": "bg"|"ink", "alpha": float|None, "panel": bool, "ratio": float}.
    Light text uses an ink scrim, dark text a bg scrim; pick the option with the smaller alpha
    (ties go to light text); if neither reaches the threshold at alpha <= MAX_SCRIM, panel=True."""
    need = AA_LARGE if size_pt >= 24 else AA_BODY
    ink, bg = hex_rgb(ink_hex), hex_rgb(bg_hex)
    light = _min_alpha(pixels, bg, ink, need)
    dark = _min_alpha(pixels, ink, bg, need)
    options = [(a, name, txt, scr) for a, name, txt, scr in ((light, "bg", bg, ink), (dark, "ink", ink, bg)) if a is not None]
    if not options:
        return {"text": "ink", "alpha": None, "panel": True, "ratio": 0.0}
    a, name, txt, scr = min(options, key=lambda o: (o[0], o[1] != "bg"))
    ratio = min(contrast(txt, _blend(p, scr, a)) for p in pixels)
    return {"text": name, "alpha": a, "panel": False, "ratio": round(ratio, 2)}


def slide_box_to_image_px(text_box, pic_box, img_size, crop):
    """Map a slide-inch text box to image pixels for a picture placed at pic_box with native crop fractions."""
    tx, ty, tw, th = text_box
    px, py, pw, ph = pic_box
    iw, ih = img_size
    l, t, r, b = crop
    vis_w, vis_h = iw * (1 - l - r), ih * (1 - t - b)
    sx, sy = vis_w / pw, vis_h / ph
    ox, oy = iw * l, ih * t
    return (ox + (tx - px) * sx, oy + (ty - py) * sy, ox + (tx + tw - px) * sx, oy + (ty + th - py) * sy)
