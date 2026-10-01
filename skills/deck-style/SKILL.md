---
name: deck-style
description: Build 3 style candidates from a reference (pptx, image, URL, template site) or a built-in preset, have the user compare them as real rendered images, then lock the fonts and colors of the chosen style into style.json. Second stage of /deck; normally invoked by /deck.
argument-hint: "[decks/<slug> folder]"
---

# deck-style

Working folder W: $ARGUMENTS (`W/brief.md` must exist)
Run scripts with `python`, or `python3` if it is missing. Wrap every path in a command in double quotes.

Talk to the user in the user's language (e.g. Korean if they write in Korean).

Resuming: if only one candidate folder among A-D in `W/candidates/` is left (`_ref` and `F*` are not counted), the selection is done. Start from step 3 using that candidate's style.json.

Reference paths:
- Scripts: `python "${CLAUDE_PLUGIN_ROOT}/scripts/<name>.py"`
- Rules: `${CLAUDE_PLUGIN_ROOT}/rules/tells.md`. Read "0. Core principles" and the C and T families first.
- Presets: `style.json`, `recipe.md` (the first line is the summary), and `thumb.png` (look at it with Read when choosing) in `${CLAUDE_PLUGIN_ROOT}/presets/<name>/`
  - `report-grid`: Korean corporate report convention (title / governing message / body). For business, internal reports, proposals
  - `keynote-type`: big type, one sentence per slide. For tech talks, conferences, keynotes
  - `academic-figure`: academic-talk style where figures and tables are the stars. For research, paper presentations, lab meetings
- User settings: `${CLAUDE_PLUGIN_DATA}/prefs.json` (may not exist)
- Saved styles: if `${CLAUDE_PLUGIN_DATA}/styles/*.json` exist, they can be used as candidates like presets.

**Principle:** never show the user the raw style.json. Always show styles as **rendered images**.

## 1. Reference analysis (in the order of the brief's references)

| Input | Method |
|---|---|
| pptx | Pull colors, fonts, sizes, and margins with `extract_pptx_style.py "<file>"`. For layout and motifs, capture with `render.py "<file>" --out "W/candidates/_ref" --width 960` and look yourself |
| Image | Look with Read and write down: colors (estimated hex), type family (serif/sans-serif, weight, size contrast), grid and margins, motifs |
| URL | If a browser tool is available, capture and look. If not, pull colors and fonts from the HTML/CSS with WebFetch |
| SlidesCarnival, Slidesgo theme pages, Microsoft Create | Open **only that one page** the user gave. No searching, list crawling, or file downloads |
| Canva, Miricanvas, Mangoboard, Google Slides templates | **No automatic access** (terms of service). Ask the user for a screenshot and handle it as an image |
| "Find one on the web" | Search with WebSearch, but open only the sites allowed in the table above, as single pages. If it fails, fall back to presets and tell the user so |

- What you take from a reference is only attributes such as **color, typography, grid, margins, and motifs**. Do not take logos, illustrations, photos, or template files.
- If the user says they will download and use a template file themselves, tell them the conditions.
  - Slidesgo free: the credits slide must be kept.
  - SlidesCarnival: attribution and a link are required.
  - Mangoboard free: the watermark must be kept.

## 2. Three candidates

### How to choose the candidates
- **If there is a reference**
  - A: faithful reproduction
  - B: refined. Remove the reference's AI tells and weaknesses.
  - C: a bold variation. Keep the same impression but change layout and contrast.
- **If there is no reference**
  - Pick 3 different families that fit the brief. Choose by the first line of the preset recipe.md, and you may adjust color and scale to fit the brief.

### Diversity rules
- **With no reference:** the three candidates must differ in **two or more** of cover type, color temperature, and typographic contrast. Giving them different `layout` (the default body composition) also makes comparison easier.
- **With a reference:** C must differ from A in two or more of those axes.
- A candidate's `structure` follows the brief's structure suggestion.
- Unless the user wants it, do not use these "second-order defaults".
  - Cream/beige background + serif + terracotta
  - Black background + one acid-green or vermilion accent
  - A hairline-only newspaper look
- Do not use purple/indigo gradients (C1) or dark + neon (C4) either.

### Fonts
- If prefs.json has fonts, use those fonts.
- Otherwise use the candidate style's fonts. For an uninstalled font, sample_deck renders with an installed fallback and tells you with a `[sample]` message (in samples only. Real decks do no substitution).

### Prepare the files
- Per-candidate style: `W/candidates/<A|B|C>/style.json` (schema at the bottom)
- Shared sample: `W/candidates/sample.json`. Fill it with the **brief's real content**.
```json
{"title": "...", "subtitle": "...", "meta": "2026.10 ○○ Seminar · Presenter",
 "claim": "Title as a claim sentence", "governing": "One sentence when structure=governing",
 "points": ["Evidence 1", "Evidence 2", "Evidence 3"],
 "number": {"value": "410ms", "label": "What the figure measures"},
 "figure": {"caption": "Figure description", "kind": "bar", "categories": ["..."],
            "series": {"Series": [1, 2]}, "highlight": 1, "source": "Source", "n": 120},
 "chart": {"title": "Conclusion sentence of the chart", "kind": "column", "caption": "Chart description",
           "categories": ["..."], "series": {"Series": [1, 2, 3]}, "highlight": 2,
           "source": "Source", "n": 120, "takeaway": "One-line interpretation"},
 "source": "Source of the points/number figures"}
```
sample.json rules (same as sample_deck.py):
- **Required:** `title`, `claim`, `points` (a string or a list of strings; an error if empty), `chart{title, categories, series}`
- **Optional:** `subtitle`, `meta`, `governing`, `number`, `figure`, `source`, `image`, `image_focus`, `chart.source/takeaway/highlight/kind/caption/n`
- `number` is given as a string like `"410ms"` or as `{value, label}`.
- `figure{categories, series, caption, kind, highlight, source, n}`: for `layout: figure`, which uses a figure in the body.
- If the style's `layout` is `statement` but there is no `number`, or it is `figure` but there is no `figure`, the sample falls back to the split body and prints a warning. To test the candidate's layout, fill in that key.
- **Do not invent `n` or figures.** Use only facts in the brief. Put `n` only when the brief has a sample size.
- If there is no source, leave `source` empty. sample_deck prints "[source needed]" ("[출처 필요]" in Korean decks).
- If the title and claim contain no Hangul, the sample is built as an English deck (Figure/Source labels).
- To test an image cover, add `"image"` (a path relative to sample.json, or absolute) and `"image_focus"` ([x0, y0, x1, y1], 0-1).

### Render
For each candidate (B and C the same way), build the sample and render it.
```
python "${CLAUDE_PLUGIN_ROOT}/scripts/sample_deck.py" "W/candidates/A/style.json" "W/candidates/sample.json" "W/candidates/A/sample.pptx"
python "${CLAUDE_PLUGIN_ROOT}/scripts/render.py" "W/candidates/A/sample.pptx" --out "W/candidates/A/renders" --width 960
```
- If sample_deck exits with code 1 and a `[sample] ...` error, fix sample.json or style.json and run again.
- If render.py ends with exit code 2, no renderer is available. Stop and relay the printed install instructions to the user.
- For any other script failure, relay the error message and stop.

Merge the three candidates into one comparison image.
```
python "${CLAUDE_PLUGIN_ROOT}/scripts/sheet.py" --rows "W/candidates/A/renders" "W/candidates/B/renders" "W/candidates/C/renders" --labels A B C --out "W/candidates/compare.png"
```

### Show them
1. First look at compare.png yourself with Read. If anything is broken, such as overflow, overlap, or weak contrast, fix it before showing.
2. If the SendUserFile tool is available, send compare.png. If not, open it in the OS viewer and tell the user the path.
   - Windows PowerShell: `Invoke-Item "<path>"`
   - Windows cmd and Git Bash: `start "" "<path>"`
   - macOS: `open "<path>"`
   - Linux: `xdg-open "<path>"`
3. Describe each candidate in one line (impression, what it fits). Then have the user choose.
4. If they ask for a mix such as "A's colors on B", make a candidate D and show it rendered the same way.
5. **As soon as the choice is final**, delete the candidate folders not chosen and `candidates/_ref`.

## 3. Lock the details
Whenever something changes, re-render the sample and show it as an image.

### 1) Fonts
- If prefs.json has fonts, propose them first: "Shall we go with ○○ again?"
- If there are none, or the user wants to change:
  1. Check the installed fonts. If the brief language is ko, use `python "${CLAUDE_PLUGIN_ROOT}/scripts/fonts.py" list --hangul`; if en, use `fonts.py list` (use the Hangul glyph filter for ko only). If the list is long, narrow it with `--grep <name>`.
  2. Pick 2-3 candidates that fit the style family.
     - Leave Inter, Roboto, Arial, Poppins, Montserrat, Space Grotesk, Instrument Serif, Geist, Aptos, Calibri, and Malgun Gothic (맑은 고딕) out of the default candidates. If the user names one, use it as is.
     - Do not put the same font first every time.
  3. Use the family value printed by fonts.py as the font name, exactly.
- Make a comparison image.
  - For each candidate, `sample_deck.py "<style>" "<sample>" "W/candidates/F<n>/sample.pptx" --font "<font>"`
  - Then render, and finally gather them on one sheet with `sheet.py --rows "<folder>" ... --labels 1 2 3 --out "<png>"`.
- Free fonts from the catalog (installed or not): `python "${CLAUDE_PLUGIN_ROOT}/scripts/fonts.py" catalog --script ko --role head` (`--script ko|latin`, `--role head|body|mono`; add `--json` for details). Use `ko` when the brief language is ko, otherwise `latin`. Mix installed and not-installed picks in the 2-3 candidates (installed only if the user declined network use), and vary the first suggestion. Show the catalog `note` when there is one (e.g. SUIT: recipients without the font open embedded decks read-only).
- For a not-installed pick, install it BEFORE making the comparison image: consent (network download, per /deck), then `python "${CLAUDE_PLUGIN_ROOT}/scripts/fonts.py" install <id>` (one at a time). If PowerPoint is open, ask the user to restart it and wait. If it exits 1 (manual entry, Store Python, or failed download) relay the message and its official URL and ask the user to install it themselves.
- Tell them that if the recipient's PC lacks this font, it will be substituted. No automatic embedding. If needed, tell them to turn on File > Options > Save > "Embed fonts in the file" in PowerPoint and save.

### 2) Color, cover, structure
Change only when the user wants: fine color tuning, cover type (type/band/image), structure (assertion/governing), default body composition (layout).

### 3) Logo and footer
Ask whether a logo and footer are needed. The event name and page number in the footer are included by default.
If there is a logo file, add its path to the `Images:` line of `W/brief.md` with `(logo)` appended.

## 4. Finalize
- Save `W/style.json`. Record the origin (preset or reference) in the `source` field.
  - Before saving, check that each font family is in the `fonts.py list` output. If not, ask the user.
- Delete `W/candidates/` entirely (including the `F*` font comparison folders).
- Update `${CLAUDE_PLUGIN_DATA}/prefs.json`.
  - Create the folder if it is missing. Keep existing keys and overwrite only the changed values.
  - Format: `{"fonts": {"head": ..., "body": ..., "mono": ...}}`
- If the user says "save this style", copy it to `${CLAUDE_PLUGIN_DATA}/styles/<name>.json`.

## style.json schema
```json
{
  "name": "short-name",
  "mood": "One-sentence impression + what it fits",
  "canvas": {"ratio": "16:9 | 4:3", "margin": 0.6},
  "color": {"bg": "#FFFFFF", "ink": "#1A1D23", "muted": "#6A7280", "accent": "#1D4E89"},
  "font": {"head": "family", "body": "family", "mono": "family"},
  "scale": {"head": 44, "title": 28, "governing": 20, "body": 18, "caption": 12, "mono": 14},
  "rhythm": {"line_height": 1.35, "tracking_head": -0.03, "tracking_body": -0.015},
  "cover": "type | band | image",
  "structure": "assertion | governing",
  "layout": "split | statement | figure",
  "motifs": ["Motifs to keep to the end of the deck"],
  "avoid": ["Rule IDs to be especially careful about in this style"],
  "source": "preset:<name> | ref:<file/URL>"
}
```
- `layout` is the default composition family of body slides (`split` if omitted).
  - `split`: evidence list and a big number side by side
  - `statement`: one sentence or one very big number
  - `figure`: centered on a figure and caption (Figure N.)
- If `font.mono` is omitted, the body font is used.
- If `canvas.title_box` [x, y, w, h] is omitted, it becomes [margin, 0.4, width − 2·margin, 1.1].
- The contrast between bg and ink must be WCAG AA or better. accent must be dark enough to read as text on bg.
