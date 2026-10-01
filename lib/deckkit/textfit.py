"""Text width/height estimation and automatic text-size fitting. Imitates PowerPoint's ko-KR word-level line breaking."""
import re

from PIL import ImageFont

_WIDE = re.compile(r"[\u1100-\u11ff\u3040-\u30ff\u3000-\u303f\u3130-\u318f\u4e00-\u9fff\uac00-\ud7a3\uff00-\uffef]")
_SCALE = 4       # measuring resolution: 1pt = 4px
SAFETY = 0.95    # margin that absorbs renderer differences


class Measurer:
    def __init__(self, font_ref=None, size_pt=18, tracking_em=0.0):
        """font_ref: (path, index) or None."""
        self.size = size_pt
        self.track = tracking_em * size_pt
        self.font = ImageFont.truetype(font_ref[0], max(1, round(size_pt * _SCALE)), index=font_ref[1]) if font_ref else None

    def width(self, s):
        """String width (pt). With no font file, estimates Hangul/CJK at 1em, a space at 0.3em, everything else at 0.55em."""
        if not s:
            return 0.0
        if self.font:
            base = self.font.getlength(s) / _SCALE
        else:
            base = sum(self.size * (1.0 if _WIDE.match(c) else 0.3 if c == " " else 0.55) for c in s)
        return base + self.track * len(s)

    def line_height(self, spacing):
        # PowerPoint's proportional line spacing is 1.2 x size x ratio regardless of font (measured on 6 fonts)
        return self.size * 1.2 * spacing


def wrap(text, m, max_w):
    """Word-level (whitespace) line breaking. A word longer than a line is cut per character (same as PowerPoint)."""
    lines = []
    for para in re.split("[\n\v]", text):  # \v is a line break inside one paragraph
        cur = ""
        for word in para.split():
            cand = f"{cur} {word}" if cur else word
            if m.width(cand) <= max_w:
                cur = cand
                continue
            if cur:
                lines.append(cur)
            while m.width(word) > max_w and len(word) > 1:
                lo, hi = 1, len(word) - 1  # binary-search the longest prefix (at least 1 char)
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    if m.width(word[:mid]) <= max_w:
                        lo = mid
                    else:
                        hi = mid - 1
                lines.append(word[:lo])
                word = word[lo:]
            cur = word
        lines.append(cur)
    return lines


def text_height(paragraphs, m, max_w, spacing, para_gap):
    lines = sum(len(wrap(p, m, max_w)) for p in paragraphs)
    return lines * m.line_height(spacing) + para_gap * max(0, len(paragraphs) - 1)


def fit_size(paragraphs, font_ref, start_pt, min_pt, box_w_in, box_h_in, spacing, tracking_em,
             para_gap_ratio=0.0, indent_pt=0.0):
    """Largest size (pt) that fits the box, and whether it succeeded. On failure, (a size near min_pt, False)."""
    size = start_pt
    while True:
        m = Measurer(font_ref, size, tracking_em)
        h = text_height(paragraphs, m, (box_w_in * 72 - indent_pt) * SAFETY, spacing, size * para_gap_ratio)
        if h <= box_h_in * 72 * SAFETY:
            return size, True
        if size - 1 < min_pt:
            return size, False
        size -= 1


def has_broken_word(paragraphs, font_ref, size_pt, box_w_in, tracking_em):
    """True if a word is longer than the box width (the word gets cut mid-line)."""
    m = Measurer(font_ref, size_pt, tracking_em)
    return any(m.width(w) > box_w_in * 72 * SAFETY for p in paragraphs for w in p.split())
