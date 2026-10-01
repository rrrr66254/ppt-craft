"""Build 3 sample slides (cover, content, data) for a style candidate. Used for candidate comparison and preset thumbnails.
Usage: python sample_deck.py <style.json> <sample.json> <out.pptx> [--font FONT]
--font: build with the head/body font replaced (for font comparison).
If a style font is not installed, it is replaced with an installed fallback and reported (samples only).

sample.json schema
  required: title, claim, points (string or list of strings, an error if empty),
            chart{title, categories, series}
  optional: subtitle, meta, governing,
            number{value, label}      (without it, a statement layout falls back to the split body)
            figure{categories, series, caption, kind, highlight, source, n}
                                      (body figure for the figure layout. Without it, falls back to the split body)
            source (body source; "[source needed]" if absent), image, image_focus,
            chart.source / takeaway / highlight / kind / caption / n
If the title and claim contain no Hangul, builds an English deck (Figure/Source labels)."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from deckkit import Deck, load_style  # noqa: E402
from deckkit.fonts import find_font_file  # noqa: E402
from deckkit.textfit import SAFETY, Measurer, wrap  # noqa: E402

FALLBACKS = ("Pretendard", "SUIT", "Noto Sans KR", "Malgun Gothic", "Apple SD Gothic Neo", "NanumGothic")
LABELS = {
    "ko": {"figure": "그림", "source": "출처", "need": "[출처 필요]"},
    "en": {"figure": "Figure", "source": "Source", "need": "[source needed]"},
}

# measurements used for body placement (inches)
GOV_H = 0.8          # height of the governing-message line
GOV_STEP = 1.0       # gap from the governing message to where the body starts
FOOT_GAP = 0.4       # minimum gap between the source line and the footer
CHART_GAP = 0.08     # between the chart and the caption/source below it
CAP_GAP = 0.05       # between the caption and the source line
SRC_H = 0.3          # height of the source-line box
MIN_CHART_H = 2.0
SPLIT_RULE_GAP, SPLIT_NUM_H, SPLIT_LABEL_H = 0.25, 1.0, 0.4   # split: rule -> number -> label
SPLIT_BLOCK = SPLIT_RULE_GAP + SPLIT_NUM_H + 0.05 + SPLIT_LABEL_H
STMT_NUM_H, STMT_LABEL_H, STMT_GAP = 1.8, 0.4, 0.1            # statement: big number -> label
STMT_BLOCK = STMT_NUM_H + STMT_GAP + STMT_LABEL_H
STMT_NUM_SCALE = 1.6  # number size = head size x 1.6


def resolve_fonts(style, font=None):
    st = load_style(style)
    if font:
        st["font"]["head"] = st["font"]["body"] = st["font"]["mono"] = font
    told = set()
    for role in ("head", "body", "mono"):
        family = st["font"][role]
        if find_font_file(family) is None:
            sub = next((f for f in FALLBACKS if find_font_file(f) is not None), None)
            if sub:
                if family not in told:
                    told.add(family)
                    print(f"[sample] '{family}' is not installed: the sample is rendered with '{sub}'")
                st["font"][role] = sub
    return st


def _prepare(sample):
    """Check the required fields and return a copy with points normalized to a list."""
    if not isinstance(sample, dict):
        raise ValueError("the top level of sample.json must be an object")
    for key in ("title", "claim", "points", "chart"):
        if not sample.get(key):
            raise ValueError(f"sample.json is missing the {key} field")
    for name in ("chart", "figure"):
        c = sample.get(name)
        if c:
            if not isinstance(c, dict):
                raise ValueError(f"{name} in sample.json must be an object")
            for key in (("title",) if name == "chart" else ()) + ("categories", "series"):
                if not c.get(key):
                    raise ValueError(f"{name} in sample.json is missing the {key} field")
    number = sample.get("number")
    if isinstance(number, (str, int, float)) and not isinstance(number, bool) and str(number).strip():
        number = {"value": str(number)}  # a bare value such as "number": "410ms" is also accepted
    if number and not (isinstance(number, dict) and number.get("value")):
        raise ValueError("number in sample.json is missing the value field")
    points = [sample["points"]] if isinstance(sample["points"], str) else list(sample["points"])
    points = [str(p) for p in points if str(p).strip()]
    if not points:
        raise ValueError("points in sample.json is empty")
    return {**sample, "points": points, **({"number": number} if number else {})}


def _lang(s):
    return "ko" if any("가" <= ch <= "힣" for ch in s["title"] + s["claim"]) else "en"


def build(style, sample, out):
    s = _prepare(sample)
    lang = _lang(s)
    d = Deck(style, lang=lang)
    labels = LABELS[lang]
    _cover(d, s)
    _content(d, s, labels)
    _data(d, s, labels)
    return d.save(out)


def _cover(d, s):
    cover = d.style["cover"]
    if cover == "image" and not s.get("image"):
        d._warn("cover=image but sample.image is missing; fell back to the type cover")
        cover = "type"
    x, w = d.col(0, 9)
    narrow = d.col(0, 7)[1]  # title/subtitle width. On the image cover it stays inside the white panel
    meta_y = d.H - d.m - 0.3
    if cover == "band":
        band_h = d.H * 0.55
        slide = d.slide(s["title"], box=(x, 1.0, w, band_h - 1.4), role="head", color="bg")
        d.send_to_back(slide, d.rect(slide, (0, 0, d.W, band_h), "accent"))
        top, sub_color, meta_color, meta_w = band_h + 0.35, "ink", "muted", w
    elif cover == "image":
        y0 = d.H * 0.52 + 0.3
        slide = d.slide(s["title"], box=(x, y0, narrow, 1.4), role="head")
        d.send_to_back(slide, d.rect(slide, (0, d.H * 0.52, d.W * 0.62, d.H * 0.48), "bg"))
        d.send_to_back(slide, d.image(slide, (0, 0, d.W, d.H), s["image"], focus=s.get("image_focus")))
        top, sub_color, meta_color, meta_w = y0 + 1.4 + 0.1, "muted", "muted", narrow
    else:
        slide = d.slide(s["title"], box=(x, d.H * 0.30, w, 2.2), role="head")
        top, sub_color, meta_color, meta_w = d.H * 0.30 + 2.35, "muted", "accent", w
    if s.get("subtitle"):
        d.text(slide, (x, top, narrow, max(0.4, meta_y - top - 0.1)), s["subtitle"], "body", color=sub_color)
    if s.get("meta"):
        d.text(slide, (x, meta_y, meta_w, 0.3), s["meta"], "caption", color=meta_color, fit=False)


def _source_text(c, labels):
    src = c.get("source")
    text = f"{labels['source']}: {src}" if src else labels["need"]
    return text + (f" · n = {c['n']}" if c.get("n") else "")


def _line_h(d, role="caption"):
    return d.style["scale"][role] * 1.2 * d.style["rhythm"]["line_height"] / 72


def _lines(d, text, width, role="caption"):
    st = d.style
    m = Measurer(find_font_file(st["font"]["body"]), st["scale"][role], st["rhythm"]["tracking_body"])
    return len(wrap(text, m, width * 72 * SAFETY))


def _chart_block(d, slide, top, x, w, c, lab, *, kind, no=None, **kw):
    """Chart + (figure-number caption) + source line. Sets the chart height so the whole block ends within FOOT_GAP above the footer.
    Returns the chart height."""
    caption = cap_h = 0
    if no is not None:
        caption = f"{lab['figure']} {no}. {c.get('caption') or next(iter(c['series']))}"
        cap_h = _lines(d, caption, w) * _line_h(d)
    block = (cap_h + CAP_GAP if caption else 0) + SRC_H
    foot_top = d.H - d.m - 0.3
    h = max(MIN_CHART_H, foot_top - FOOT_GAP - top - CHART_GAP - block)
    d.chart(slide, (x, top, w, h), kind, c["categories"], c["series"], highlight=c.get("highlight"), **kw)
    y = top + h + CHART_GAP
    if caption:
        d.text(slide, (x, y, w, cap_h + 0.04), caption, "caption", color="ink")
        y += cap_h + CAP_GAP
    d.text(slide, (x, y, w, SRC_H), _source_text(c, lab), "caption", color="muted", fit=False)
    return h


def _content(d, s, labels):
    slide = d.slide(s["claim"])
    top = d.content_top
    layout = d.style["layout"]
    if layout == "statement" and not s.get("number"):
        d._warn("layout=statement but sample.number is missing; fell back to the split body")
        layout = "split"
    if layout == "figure" and not s.get("figure"):
        d._warn("layout=figure but sample.figure is missing; fell back to the split body (so the same chart is not shown twice)")
        layout = "split"
    if d.style["structure"] == "governing" and s.get("governing"):
        x, w = d.col(0, 12)
        d.text(slide, (x, top, w, GOV_H), s["governing"], "governing", color="muted")
        top += GOV_STEP
    _CONTENT[layout](d, slide, s, top, labels)
    notes = list(s["points"][1:]) if layout == "statement" else []  # one sentence per slide: the remaining points go into the speaker notes
    notes.append(f"{labels['source']}: {s['source']}" if s.get("source") else labels["need"])
    d.notes(slide, "\n".join(notes))
    d.footer(slide, s.get("meta", ""), 2)


def _split_content(d, slide, s, top, labels):
    """7+4 asymmetric: evidence list on the left, a big number with a thin rule above it on the right. Both are vertically centered in the area.
    Without a number, the list uses 8 columns."""
    num = s.get("number")
    d.text(slide, d.body_box(0, 7 if num else 8, top=top), s["points"], "body", bullets=True, anchor="middle")
    if num:
        x, w = d.col(8, 4)
        y = top + (d.content_bottom - top - SPLIT_BLOCK) / 2
        d.rule(slide, x, y, w, color="ink", weight=0.75)
        d.text(slide, (x, y + SPLIT_RULE_GAP, w, SPLIT_NUM_H), num["value"], "head", color="accent")
        if num.get("label"):
            d.text(slide, (x, y + SPLIT_BLOCK - SPLIT_LABEL_H, w, SPLIT_LABEL_H), num["label"], "caption", color="muted")


def _statement_content(d, slide, s, top, labels):
    """One sentence + a very big number: the number is vertically centered in the left 7 columns, the supporting line is bottom-aligned in the right 4 columns."""
    num = s["number"]
    y = top + (d.content_bottom - top - STMT_BLOCK) / 2
    x, w = d.col(0, 7)
    d.text(slide, (x, y, w, STMT_NUM_H), num["value"], "head", color="accent", anchor="bottom",
           size=d.style["scale"]["head"] * STMT_NUM_SCALE)
    label_h = STMT_LABEL_H
    if num.get("label"):
        d.text(slide, (x, y + STMT_NUM_H + STMT_GAP, w, STMT_LABEL_H), num["label"], "body", color="muted")
        label_h = _line_h(d, "body")
    x, w = d.col(8, 4)
    d.text(slide, (x, y, w, STMT_NUM_H + STMT_GAP + label_h), s["points"][0], "body", anchor="bottom")  # aligned to the label's baseline


def _figure_content(d, slide, s, top, labels):
    """Figure in 8 columns + interpretation in 4. Below the figure, a "Figure N." caption and the source."""
    fig = s["figure"]
    x, w = d.col(0, 8)
    h = _chart_block(d, slide, top, x, w, fig, labels, kind=fig.get("kind", "bar"), no=1)  # the default for a body figure is a horizontal bar chart
    x, w = d.col(8, 4)
    d.text(slide, (x, top, w, h), s["points"], "body", bullets=True)


_CONTENT = {"split": _split_content, "statement": _statement_content, "figure": _figure_content}


def _data(d, s, labels):
    c = s["chart"]
    slide = d.slide(c["title"])
    layout = d.style["layout"]
    top = d.content_top
    kind = c.get("kind", "column")
    if layout == "statement":
        x, w = d.col(0, 12)
        _chart_block(d, slide, top, x, w, c, labels, kind=kind, labels=True)
        if c.get("takeaway"):  # the title is already the conclusion, so it is not written separately on the slide
            d.notes(slide, c["takeaway"])
    elif layout == "figure":
        x, w = d.col(0, 8)
        h = _chart_block(d, slide, top, x, w, c, labels, kind=kind, no=2 if s.get("figure") else 1)  # without a figure body, this figure is the first one
        if c.get("takeaway"):
            x, w = d.col(8, 4)
            d.text(slide, (x, top, w, 1.0), c["takeaway"], "body")
    else:
        x, w = d.col(0, 8)
        h = _chart_block(d, slide, top, x, w, c, labels, kind=kind)
        if c.get("takeaway"):
            x, w = d.col(9, 3)
            d.text(slide, (x, top, w, h), c["takeaway"], "governing", anchor="middle")
    d.footer(slide, s.get("meta", ""), 3)


def main(argv=None):
    ap = argparse.ArgumentParser(description="3 style sample slides")
    ap.add_argument("style")
    ap.add_argument("sample")
    ap.add_argument("out")
    ap.add_argument("--font")
    a = ap.parse_args(argv)
    sample_path = Path(a.sample)
    try:
        sample = json.loads(sample_path.read_text(encoding="utf-8"))
        if isinstance(sample, dict) and sample.get("image") and not Path(sample["image"]).is_absolute():
            sample["image"] = str((sample_path.parent / sample["image"]).resolve())
        print(build(resolve_fonts(a.style, a.font), sample, a.out))
    except (ValueError, OSError) as e:  # JSONDecodeError is a ValueError. A missing file or image is an OSError
        print(f"[sample] {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    sys.exit(main())
