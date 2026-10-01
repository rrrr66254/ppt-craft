"""Image crop math. Produces PowerPoint native crop (srcRect) ratios; the original stays in the file,
so the user can re-adjust it with PowerPoint's Crop tool."""


def cover_crop(img_w, img_h, slot_w, slot_h, focus=None, must_keep=None, anchor="center"):
    """Crop ratios (left, top, right, bottom) that fill the slot completely. None if must_keep cannot be honored.

    focus, must_keep: (x0, y0, x1, y1) as 0-1 ratios of the image.
    anchor: "center" puts the focus at the window center, "thirds" at a rule-of-thirds point.
    """
    aspect = slot_w / slot_h
    if img_w / img_h > aspect:
        win_w, win_h = img_h * aspect, float(img_h)
    else:
        win_w, win_h = float(img_w), img_w / aspect
    fx0, fy0, fx1, fy1 = focus or (0.0, 0.0, 1.0, 1.0)
    x0 = _place((fx0 + fx1) / 2 * img_w, win_w, img_w, anchor)
    y0 = _place((fy0 + fy1) / 2 * img_h, win_h, img_h, anchor)
    if must_keep:
        kx0, ky0 = must_keep[0] * img_w, must_keep[1] * img_h
        kx1, ky1 = must_keep[2] * img_w, must_keep[3] * img_h
        if kx1 - kx0 > win_w + 1e-6 or ky1 - ky0 > win_h + 1e-6:
            return None
        x0 = _clamp(min(max(x0, kx1 - win_w), kx0), 0.0, img_w - win_w)
        y0 = _clamp(min(max(y0, ky1 - win_h), ky0), 0.0, img_h - win_h)
    return (
        _ratio(x0, img_w),
        _ratio(y0, img_h),
        _ratio(img_w - x0 - win_w, img_w),
        _ratio(img_h - y0 - win_h, img_h),
    )


def contain_box(img_w, img_h, box):
    """Placement (x, y, w, h) centered inside box (x, y, w, h) without cropping."""
    x, y, w, h = box
    s = min(w / img_w, h / img_h)
    cw, ch = img_w * s, img_h * s
    return (x + (w - cw) / 2, y + (h - ch) / 2, cw, ch)


def effective_dpi(img_w, crop, slot_w_in):
    """Visible pixel width after cropping / slot width (inches)."""
    left, _, right, _ = crop
    return img_w * (1 - left - right) / slot_w_in


def _place(center, win, total, anchor):
    if anchor == "thirds" and win < total - 1e-6 and abs(center - total / 2) >= 1e-6:
        start = center - win / 3 if center < total / 2 else center - win * 2 / 3
    else:
        start = center - win / 2
    return _clamp(start, 0.0, total - win)


def _clamp(v, lo, hi):
    return max(lo, min(v, hi))


def _ratio(px, total):
    return max(0.0, round(px / total, 6))
