# deckkit API (for writing build.py)

```python
from deckkit import Deck
d = Deck("style.json")          # path relative to the folder containing build.py
d = Deck("style.json", lang="en")  # English deck: the chart source label becomes "Source" and ko-KR is not set on chart fonts (default "ko")
```
- All coordinates are in **inches**, and a box is `(x, y, w, h)`.
- Colors are `"bg" | "ink" | "muted" | "accent"` or `"#RRGGBB"`.
- Roles: `head` (cover, big number, one sentence), `title`, `governing`, `body`, `caption`, `mono`
- An invalid role, align, anchor, or color raises `ValueError`. Fix it as the message says.
- Language: Hangul runs automatically get `lang="ko-KR"` plus the ea font, and Korean decks use `Deck(..., lang="ko")` (the default). English decks pass `lang="en"`.

| Method | Description |
|---|---|
| `d.col(start, span, cols=12, gutter=0.25)` → `(x, w)` | 12-column grid. start is 0-based |
| `d.body_box(start=0, span=12, top=None, bottom=None)` → box | The area below the title and above the footer |
| `d.content_top`, `d.content_bottom`, `d.W`, `d.H`, `d.m` | Top and bottom bounds of the body, slide size, margin |
| `d.slide(title=None, *, bg="bg", box=None, role="title", color="ink", anchor="bottom")` | New slide. The title goes into the title placeholder. A `"\n"` splits the lines with no paragraph spacing. For a cover, use `box=` and `role="head"` |
| `d.text(slide, box, content, role="body", *, color="ink", bold=None, align="left", anchor="top", fit=True, bullets=False, size=None)` | content is a string or a list of paragraphs (`"\n"` also splits paragraphs). `"\v"` (vertical tab) inside a paragraph is a line break within that paragraph, so a deliberately broken sentence stays one paragraph, not a list. With `bullets=True`, paragraph bullets (never type a • character yourself). `size` (pt) is used instead of the role's default size (big numbers, etc.) |
| `d.rect(slide, box, color="muted")` | Solid block. No border, no shadow |
| `d.rule(slide, x, y, w, *, color="ink", weight=0.75)` | Horizontal line. Do not use it right under the title (L6) |
| `d.chart(slide, box, kind, categories, series, *, highlight=None, number_format="General", source=None, labels=False)` | kind: `column` `bar` `line`. series={name: values}. highlight=index of the category to emphasize (bars, single series; `ValueError` if out of range). With `labels=True`, value labels are added and the value axis is hidden. If source is given, a source line goes under the chart |
| `d.image(slide, box, path, *, fit="cover", focus=None, must_keep=None, anchor="center")` | Native crop (original preserved). focus and must_keep are the images.json values. Use `fit="contain"` for diagrams and logos (the picture sits on the box's left edge, centered vertically). If a person or object is off to one side, use `anchor="thirds"` |
| `d.icon(slide, box, svg_path, png_path=None)` | Icon from `assets.py icon get` (`<prefix>-<name>.svg` + `.png`). Editable vector in PowerPoint 2019+/365, PNG fallback elsewhere. Fits inside the box keeping aspect (contain). A missing PNG is rendered from the SVG. An SVG with external references raises `ValueError` |
| `d.callout(slide, target_box, label, label_box, *, color="accent")` | Annotation on a screenshot: border around the target + connector line + note. If the label box is placed so it does not overlap the target, the line attaches on the side with the biggest gap |
| `d.pattern(name, title, path, *, focus=None, must_keep=None, words=0, ...)` → `(slide, content_box)` | Builds a whole image slide. name: `bleed-panel` `bleed-scrim` `split` `inset` `strip` `gallery` (others raise `ValueError`, as does a name missing from `imagery.patterns`). Extra keywords: `role="head"` for a cover title (bleed-panel, bleed-scrim, split; the title box grows to fit 2-3 lines and the scrim contrast is planned at that size; default `"title"`); `side="left"` or `"right"` (text side, default opposite the focus) for bleed-*/split; `ratio=(5, 7)` (image, text columns) for split (the photo is a half-bleed: full slide height out to the slide edge, and the title stays in the text columns; `fit="contain"` keeps a figure inside the content area); `caption=` (required) for inset; `position`, `height_ratio` (≤ 0.4) for strip; gallery takes a list of 2-4 paths plus `captions=`, `hero=`. `content_box` is where body text goes, or None. bleed-scrim's solid scrim is a full-height band from the text-side slide edge. It falls back to bleed-panel with a warning when contrast fails or there are more than 15 words |
| `d.text_color` | `"ink"` or `"bg"`: the body-text color for the slide `d.pattern` just built. Pass it as `color=` to every text on that slide |
| `suggest(image, role, words=0, n_images=None, prev=(), imagery=None, bleed_used=0)` (`from deckkit.patterns import suggest`) | Up to 2 ranked `{"pattern", "reason", "params"}`. image: the images.json entry (or None), role: `cover` `section` `statement` `evidence` `comparison` `detail`, prev: patterns of the previous 2 slides, imagery: `d.style["imagery"]`. Pass `params` on to `d.pattern`. `figure`/`annotated`/`type-only` are built by hand (below) |
| `d.background(slide, path, *, focus=None, must_keep=None)` | Full-bleed picture behind everything (tagged pc:bleed, counts toward `imagery.max_bleed`). Prefer `d.pattern("bleed-panel"/"bleed-scrim", ...)`, which also handles text contrast |
| `d.scrim(slide, box, *, color="ink", alpha=0.45)` | Solid translucent rectangle over a photo, 0 < alpha ≤ 0.7. Never a gradient |
| `d.texture(slide, png_path)` | Texture from `imagefx.py texture` behind everything (tagged pc:texture, not counted toward max_bleed). One cover or section slide only (C13) |
| `d.send_to_back(slide, shape)` | Send a background block or photo to the very back. Pass the shape that `d.rect`, `d.image`, or `d.text` returns |
| `d.notes(slide, text)` | Speaker notes |
| `d.footer(slide, left="", page=None)` | Footer (event name and date on the left, page number on the right). 0.3in tall, right below the body area. On a split slide both stay on the text side |
| `d.save("out.pptx")` | Save. If `[deckkit warning]` is printed, resolve every one |

Chart rules
- Do not create a chart title. The slide title carries the claim.
- In `bar` (horizontal bars), the first category comes out on top.
- Use at most 3 series. Show the unit through the series name or `number_format`.

Automatic text-size fitting: with `fit=True` (the default), the text size shrinks automatically to fit the box.
- Minimum size per role: head 28, title 20, governing 16, body 14, caption 10, mono 12 (pt)
- If it still overflows at the minimum size, a warning appears. Then do not shrink the text further; cut the content or enlarge the box.

## Image slides

```python
import json
from deckkit.patterns import suggest

images = json.load(open("assets/images.json", encoding="utf-8"))

photo = "assets/treated/platform-room-harmonize.jpg"   # treated copy (deck-build step 2.4)
entry = images["platform-room.jpg"]                      # type, size, focus, must_keep
pick = suggest(entry, "evidence", words=9, prev=["type-only", "split"], imagery=d.style["imagery"])[0]
if pick["pattern"] in ("figure", "annotated"):            # not d.pattern helpers: contained picture + caption (+ d.callout)
    s = d.slide("The new cache nodes sit in rack B4")
    x, w = d.col(0, 8)
    d.image(s, (x, d.content_top, w, 4.2), photo, fit="contain")
    d.text(s, (x, d.content_top + 4.3, w, 0.35), "Photo: Platform team, Seoul IDC, September 2026", "caption", color="muted")
elif pick["pattern"] == "type-only":
    s = d.slide("The new cache nodes sit in rack B4")
else:
    extra = {"caption": "Photo: Platform team, Seoul IDC, September 2026"} if pick["pattern"] == "inset" else {}
    s, box = d.pattern(pick["pattern"], "The new cache nodes sit in rack B4", photo,
                       focus=entry["focus"], must_keep=entry["must_keep"], words=9, **pick["params"], **extra)
    if box:
        d.text(s, box, "Two nodes, 64 GB each, added in July", color=d.text_color)
```
On full-bleed slides the footer and page number sit on the photo: leave the footer off cover and section bleeds, or check it on the render.

## Tables (not in deckkit: use python-pptx directly)

```python
from pptx.util import Inches
gf = s.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(d.content_top), Inches(w), Inches(2.4))
tbl = gf.table
tbl.first_row = tbl.horz_banding = False   # turn off the default table style (header color, banding). Draw dividing lines with d.rule
for r, row in enumerate(rows):
    for c, value in enumerate(row):
        cell = tbl.cell(r, c)
        cell.text = value
        for p in cell.text_frame.paragraphs:
            for run in p.runs:
                run.font._rPr.set("lang", "ko-KR")   # Korean decks only (omit for English). The ea font is filled in by the Deck theme
```

## Example build.py

```python
from deckkit import Deck

d = Deck("style.json", lang="en")
META = "2026.10 Internal Tech Seminar · Platform Team"

# 1. Cover: big type, left-aligned
x, w = d.col(0, 9)
s = d.slide("Three months with a cache", box=(x, d.H * 0.30, w, 2.2), role="head")
d.text(s, (x, d.H * 0.30 + 2.35, d.col(0, 7)[1], 0.8), "How we cut order API latency in half", color="muted")
d.text(s, (x, d.H - d.m - 0.3, w, 0.3), META, "caption", color="accent", fit=False)

# 2. Big-number slide (scale break): the number fills the body height, the evidence sits at the lower right
s = d.slide("Adding a cache halved p99 latency")
top, bot = d.content_top, d.content_bottom - 0.4
x, w = d.col(0, 7)
d.text(s, (x, top, w, bot - top - 0.7), "410ms", "head", size=150, color="accent", anchor="bottom")
d.text(s, (x, bot - 0.6, w, 0.5), "Order API p99 in September (820ms in July)", "caption", color="muted")
x, w = d.col(8, 4)
d.text(s, (x, top, w, bot - top), ["p99 fell from 820ms to 410ms", "83% of read requests end at the cache"], anchor="bottom", bullets=True)
d.text(s, (d.m, d.content_bottom - 0.3, d.col(0, 8)[1], 0.3), "Source: internal APM, September 2026", "caption", color="muted", fit=False)
d.notes(s, "In July we went over one second at peak. Source: internal APM, September 2026")
d.footer(s, META, 2)

# 3. Chart slide: conclusion title + one highlighted bar + value labels + source
s = d.slide("Cloud cost rose 380k KRW a month by September")
x, w = d.col(0, 8)
d.chart(s, (x, d.content_top, w, d.content_bottom - d.content_top - 0.4), "column",
        ["Jul", "Aug", "Sep"], {"Monthly cost (10k KRW)": [120, 131, 158]}, highlight=2, labels=True,
        source="Cloud invoices")
d.text(s, d.body_box(9, 3, bottom=d.content_bottom - 0.4), "The increase is the cost of 2 cache nodes", anchor="bottom")
d.footer(s, META, 3)

d.save("out.pptx")
```
