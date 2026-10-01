"""SVG safety check shared by assets.py (icon get) and Deck.icon()."""
import re

# Icons must be self-contained: no scripts, embedded images, event handlers, or references other than #fragment ids.
UNSAFE_SVG = re.compile(r"<(script|image|foreignObject)\b|\son[a-z]+\s*=|href\s*=\s*[\"']\s*[^#\s\"']|url\(\s*[\"']?\s*[^#\s\"')]", re.I)


def svg_is_safe(text):
    return not UNSAFE_SVG.search(text)


def svg_aspect(text):
    """width/height of the SVG from the root's width/height (plain numbers or px) or viewBox; None if unparseable."""
    m = re.search(r"<svg[^>]*>", text, re.I)
    root = m.group(0) if m else ""

    def attr(name):
        a = re.search(r"\s" + name + r"\s*=\s*[\"']\s*([0-9.]+)\s*(?:px)?\s*[\"']", root, re.I)
        return float(a.group(1)) if a else None  # float() may raise on '1.2.3': caught below

    try:
        w, h = attr("width"), attr("height")
        if not (w and h):
            vb = re.search(r"viewBox\s*=\s*[\"']\s*[-0-9.eE]+[\s,]+[-0-9.eE]+[\s,]+([0-9.]+)[\s,]+([0-9.]+)\s*[\"']", root)
            w, h = (float(vb.group(1)), float(vb.group(2))) if vb else (None, None)
        return w / h if w and h else None
    except (ZeroDivisionError, ValueError):  # e.g. width="1.2.3"
        return None
