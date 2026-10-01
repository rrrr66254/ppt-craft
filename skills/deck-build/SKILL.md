---
name: deck-build
description: Build the outline (outline.md) from brief.md and style.json, plan crops for user images, write build.py with deckkit, and produce out.pptx. Also applies the fix instructions from a review result (review-N.md). Third stage of /deck; normally invoked by /deck.
argument-hint: "[decks/<slug> folder]"
---

# deck-build

- Working folder W: $ARGUMENTS
- Talk to the user in the user's language (e.g. Korean if they write in Korean). File contents you write for the user (outline.md, the lines under `## Applied` in review-N.md) follow the deck's language. The heading `## Applied` itself always stays in English: /deck and fix mode look for that exact string.
- **Fix mode:** if the first line of the last `W/review-N.md` is `RESULT: FAIL` and it has no `## Applied` section yet, fix that review result. If the user's fix instructions are in the conversation, apply them the same way.
- Script run format: `python "${CLAUDE_PLUGIN_ROOT}/scripts/<name>.py"` (use `python3` if `python` is missing). Wrap every path in a command in double quotes.

**Always read these before starting.**
- `W/brief.md`, `W/style.json`
- `${CLAUDE_PLUGIN_ROOT}/rules/tells.md` (all of it)
- `${CLAUDE_PLUGIN_ROOT}/skills/deck-build/deckkit-api.md`
- If the `source` in style.json is `preset:<name>`, `${CLAUDE_PLUGIN_ROOT}/presets/<name>/recipe.md`
- Do not re-read files you already read in this conversation.

## 1. W/outline.md (two steps)

If `W/outline.md` already exists, skip this step and follow that outline (update it only when fixing in fix mode).

### 1-1. Thesis and title storyboard
Write the brief's one-line thesis, then list only the slide titles in order.

Title rules:
- Write titles as claim sentences (W4). Do not use topic labels such as "Market Overview".
- The titles alone, read in sequence, must form an argument (S2).
- Match the slide count to the number of claims (S5). If it differs a lot from the brief's length, propose an adjustment.
- The flow is problem → evidence → proposal. End the last slide on a request or a decision.
- Do not use "Thank you", "Q&A", "Key Takeaways", or "Agenda" (in Korean decks "감사합니다", "목차") as a title (S1).

How to get the user's confirmation:
- If you only got a topic, show the storyboard and get confirmation.
- If you got an outline, follow the outline. If you polished a title into a claim sentence, say that you did.

### 1-2. Per-slide detail (table)
| # | Title (claim) | Governing message (when governing) | Supporting content | Visualization type | Assets | Placement (pattern + reason) | Speaker notes | Figure source (shown on the slide as a caption line) |

Pick the visualization type from: one sentence / big number / chart / comparison table / 2×2 / process / full-bleed image / quote / diagram / annotated screenshot

- Use the same type at most 2 slides in a row (L2).
- Mark the 2-3 core slides of the argument as "scale breaks" (S4, T6).
- Put at least one of proper noun, real figure, date, or example on every slide (H1). For a slide with nothing to put in, first consider merging or dropping it.
- Take figures only from the brief's materials. If there are none, leave `[source needed]` (`[출처 필요]` in Korean decks) (D3). Never invent figures.
- If the brief has `lack of factual material`, do not make up facts to satisfy H1. A one-sentence slide leans on the fact in its title, and a slide with no facts to put in is merged or dropped.
- Mix slides of different density (H6). Do not put an image on every slide (H7).
- Placement: one pattern per slide from `style.json` `imagery.patterns` (`type-only` is always allowed), with a short reason. See "Placement" below.
- The `layout` in style.json is the **default starting point** when designing body slides. You may change it per slide to fit the content.
  - `split`: evidence list and a big number side by side
  - `statement`: one sentence or one very big number
  - `figure`: a figure and caption ("Figure N.")

## 2. Images and icons
1. Prepare the images. A copy with EXIF rotation applied and the long edge reduced to 3000px or less is created in `W/assets/`, and an entry is added to `W/assets/images.json` (the original is left as is).
   ```
   python "${CLAUDE_PLUGIN_ROOT}/scripts/images.py" "<image>" ["<image>" ...] --out "W/assets"
   ```
2. Look at each image with Read and fill the empty fields of its images.json entry (the key is the file name inside `W/assets/`). Leave `file`, `source`, `size`, `kind_guess`, and `content_bbox` as they are; the script filled them.
   - `type`: `photo | screenshot | diagram | logo`
   - `focus` [x0, y0, x1, y1] (0-1): the area that must be visible. For screenshots, use `content_bbox` as a reference and leave out window borders and margins.
   - `must_keep`: a face or text area that must not be cut off. null if none
   - `note`: what this image shows
3. Decide the placement. build.py runs in W, so paths are `assets/<file>`.
   - Photos: place with `fit="cover"` around the focus. If a person or object is off to one side, use `anchor="thirds"`
   - Diagrams: `fit="contain"`
   - Logos: files listed on the brief's `Images:` line with `(logo)` after the path. Set `type` to `logo` and put it in the **same position** on every body slide (a spot that does not overlap title, body, or footer text) with `fit="contain"`. It need not appear on the cover.
   - Screenshots: mark what to point at with `callout` (H3).
4. Treat the photos once per deck, after their images.json entries (focus especially) are filled. Only `type: photo`; never screenshots, diagrams or logos.
   - `imagery.treatment` is `gray` or `duotone`: `--mode <treatment>`.
   - `treatment` is `none` and `harmonize` is true: `--mode harmonize`.
   - Both off: skip this step.
   ```
   python "${CLAUDE_PLUGIN_ROOT}/scripts/imagefx.py" treat "W/assets/<photo>" ["W/assets/<photo>" ...] --mode <mode> --style "W/style.json" --out "W/assets/treated"
   ```
   build.py then uses `assets/treated/<stem>-<mode>.jpg` (`.png` for images with transparency). The treatment does not change geometry, so the focus and must_keep values from images.json still apply. Every photo in the deck gets the same mode (I12). Treat photos taken later with `photo get` the same way.

### Free photos, generated images, icons
Priority: the user's images first; then, as equals (the user's decision), `photo search` or `gen`; otherwise no image and a layout without one. Use an image only when it is evidence (H2, I8). Needs the network consent from /deck. Run commands one at a time.

**Photo search**
```
python "${CLAUDE_PLUGIN_ROOT}/scripts/assets.py" photo search "<query>" --out "W/assets/_cand" --n 12 --cache "${CLAUDE_PLUGIN_DATA}/cache"
```
**Generation** (does not take `--cache`). Pass `--aspect 16:9|4:3|3:2|1:1` matching the slot, `--n` for the number of candidates (1-8, default 2).
```
python "${CLAUDE_PLUGIN_ROOT}/scripts/assets.py" gen "<prompt>" --out "W/assets/_cand" --aspect 16:9 --n 2
```
- Prompt: describe a concrete environment or object, no close-up faces or hands, no confidential text (prompts go to third parties). The script drops banned AI-look words and appends a style suffix. Use `--raw` only to send the prompt exactly as written.
- `[assets] no image-generation key set …` means the keyless AI Horde was used (max 576px, small slots only). Tell the user how to get larger images: create a free Cloudflare Workers AI account, then set `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` as environment variables and restart Claude Code. Other keys the script reads: `POLLINATIONS_API_KEY`, `HF_TOKEN`. Never ask users to paste keys into chat. Never print key values to check them; the script's messages say whether a key was found.
- Few or poor photo results and no `PEXELS_API_KEY`: tell the user they can get a free Pexels key and set `PEXELS_API_KEY` the same way. `[assets] skip <source>: … not set` just means that source was left out.

**Select**
- Read every `thumb_file` listed in `_cand/candidates.json`.
- Reject I4, I5, I6, and I8 images. Be stricter with `ai_risk: true` and generated ones (garbled text, waxy skin, odd hands, over-sharpening).
- A horde image (576px or less) goes only into a small slot.

**Take it**
```
python "${CLAUDE_PLUGIN_ROOT}/scripts/assets.py" photo get "<candidate id>" --cand "W/assets/_cand" --out "W/assets" --cache "${CLAUDE_PLUGIN_DATA}/cache"
```
`photo get` also takes a generated candidate id (`gen:<provider>:<seed>`). It prints the file name and records the license in `assets/credits.json`. Then fill the images.json fields as in step 2 (focus especially). If it prints `[assets] warning: … px wide`, the record has `low_res`: use that image only in a smaller slot, or pick another.

**Icons** only when they help tell items apart faster (I1, I2), never as decoration.
```
python "${CLAUDE_PLUGIN_ROOT}/scripts/assets.py" icon search "<query>" --sets lucide --cache "${CLAUDE_PLUGIN_DATA}/cache"
python "${CLAUDE_PLUGIN_ROOT}/scripts/assets.py" icon get lucide:database --color "#RRGGBB" --out "W/assets/icons" --cache "${CLAUDE_PLUGIN_DATA}/cache"
```
- Pick one set per deck and pass only that set to `--sets` (`lucide`, or `tabler`, gives a consistent line style; do not mix sets). `--color` is the style's `ink` (or `muted`) hex; use `accent` only for the one icon that is the slide's single accent spot (C9). No colored circle or tile behind icons (I2).
- Place it with `d.icon(s, box, "assets/icons/lucide-database.svg")`.

**Failures**
- Exit 1 from `assets.py` is not fatal (nothing found, every provider failed, download failed, unknown id, icon refused), and neither is rejecting every candidate: try one changed query or prompt, or the other of `photo search`/`gen`, or another icon/set; otherwise go without the image. For `resvg-py missing`, follow /deck's install procedure. Exit 2 means a wrong command: fix it.

**Credits**
- Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/assets.py" credits "W/assets" --files` (add `--lang ko` for a Korean deck). It prints one `<file>: <line>` per record (`* ` marks required ones; drop the marker). Use only the records whose file build.py uses, map each line to the slide that uses that file by the `<file>` before the colon, and put only the `<line>` part in that slide's notes.
- If any record has `attribution_required`, `share_alike`, or `ai_generated`, add a small credits slide after the closing request/decision slide (an appendix, not part of the storyboard), listing those lines in the caption role, not titled "Thank you" (S1). For `ai_generated` records the line is a disclosure: put it in that slide's notes and on the credits slide.
- For CC BY / BY-SA images that were cover-cropped, append "(cropped)" to their credit line.

Delete nothing here: /deck's wrap-up removes `assets/_cand/`.

## 3. Write and run W/build.py

### Placement (image slides)
Decide each slide's pattern with `deckkit.patterns.suggest(...)` in build.py (or by the same order below), then record it in the outline's Placement column. The final choice is yours; suggest is the starting point.
1. No image that proves the point: `type-only` (H7, I8).
2. Diagram or logo: `figure`. Screenshot: `annotated`, then `inset`.
3. 2-4 comparable images: `gallery`. Panorama 3:1 or wider: `strip`.
4. Cover, section or one-sentence slide with one photo: `bleed-scrim` (`bleed-panel` above 15 words), while full-bleed slides stay within `imagery.max_bleed`; past that, `split`.
5. Evidence, detail, comparison: `split` or `inset`.
6. Text goes opposite the focus. Skip a pattern that the previous 2 slides both used (L2) and any pattern not in `imagery.patterns`.

How to build each pattern (API in deckkit-api.md):
- `bleed-panel`, `bleed-scrim`, `split`, `inset`, `strip`, `gallery`: `s, box = d.pattern(name, title, path, focus=..., must_keep=..., words=...)`, passing `suggest()`'s params (`side`, `ratio`). Write body text into `box` (None means no room) with `color=d.text_color`.
- `inset` needs `caption=` with provenance (source, date, place; I13). `split` defaults to `ratio=(5, 7)` (image, text columns); use `(7, 5)` when the photo is the point.
- `figure`: `d.slide(title)` + `d.image(..., fit="contain")` + a caption line with the source. `annotated`: a figure + `d.callout`. `type-only`: a plain `d.slide`.
- Full-bleed slides: the footer and page number would sit on the photo. Leave the footer off cover and section bleeds, or check its legibility on the render.
- At most `imagery.max_bleed` full-bleed slides, never the same pattern 3 slides in a row. Captions with provenance on photos and figures (I13). No drawn device frames around screenshots (I11), no shape masks that imitate a cutout (I10).
- Texture (only if `imagery.texture` is set): make it once with `imagefx.py texture --style "W/style.json" --out "W/assets/texture-<kind>.png"` and place it with `d.texture(s, path)` on one cover or section slide (C13).

### Writing rules
- Use only the API in deckkit-api.md.
  - Use python-pptx directly only for what deckkit lacks, such as tables.
  - Even then, do not create shadows, gradients, or centered body text.
  - For tables, use the code in the 'Tables' section of deckkit-api.md (turn off the default style, Hangul `lang`). Draw dividing lines with `d.rule`.
  - Put `lang="ko-KR"` and an ea font on Hangul runs.
- If the brief's language is en, create it with `Deck("style.json", lang="en")` (the default is ko).
- Save into W with `d.save("out.pptx")`.
- Design the layout **per slide to fit its content**.
  - Use asymmetric splits on the 12-column grid (7+5, 8+4, 4+8, 3+9).
  - Align left, and separate elements with whitespace.
- Banned items that get caught often
  - Three cards of icon + title + description (L1)
  - A rule under the title (L6), a left stripe on cards (L5)
  - Emoji (I3)
  - Two or more accent-color spots on one slide (C9)
  - An image on every slide (H7)
  - KPI tiles with no context (D1)
- Put the brief's event name, date, and a page number in the footer (H4). Not on the cover.
- Write speaker notes in the brief's tone, as speech (H5). For slides with figures, put a small source line (`Source: …`; in Korean decks `출처: …`) on the slide in the caption role and also in the notes (D3, H4).

### Run
```
python "${CLAUDE_PLUGIN_ROOT}/scripts/run_build.py" "W/build.py"
```
Fix build.py for build.py run errors. For `ModuleNotFoundError`, follow /deck's install procedure (if it is missing, get the user's consent and run `pip install -r "${CLAUDE_PLUGIN_ROOT}/requirements.txt"`).

If `[deckkit warning]` appears, resolve every one and run again.
| Warning | Action |
|---|---|
| Text overflow | Shorten the sentence or enlarge the box. Do not shrink text below the minimum size |
| Word broken mid-line | Widen the box or change the sentence |
| Font '…' is not installed | Stop and ask whether to switch to an installed font (style.json) or install it |
| resolution … dpi | Shrink the slot or ask for a larger original |
| fell back to contain (must_keep) | Change the slot ratio to fit the image |
| has EXIF rotation info | Normalize the image with `images.py` first |
| With more than 3 series | Split the chart, or cut to 3 series |
| highlight applies only to the first series | Use a single series, or drop highlight |
| … using bleed-panel (contrast, too many words, must_keep, could not be analyzed) | The panel is already in place. Keep it, or shorten the text, pick a photo with a quiet side, or change the pattern |
| only …px wide for a full-bleed background | Use split or inset, or get a larger photo |
| Full-bleed slides exceed imagery.max_bleed | Change one full-bleed slide to split, inset or type-only |
| Gallery without captions | Add one provenance caption per image |

### Self-check
```
python "${CLAUDE_PLUGIN_ROOT}/scripts/lint.py" "W/out.pptx" --style "W/style.json" --out "W/lint.json"
```
If the exit code is 1 (blockers or majors present), fix them all and then hand over to review. If the exit code is 2 (lint failed), stop and relay the error message to the user.
If another script such as images.py fails, relay the error message and stop.

## 4. Fix mode
- Fix **all** blockers and majors in review-N.md, and as many minors as you can. Do not fix `Lint dismissed` items.
- In fix mode, after re-running lint, if the only blocker/major findings left are ones the review listed under `## Lint dismissed`, continue to review.
- If there are user instructions instead of a review, apply them the same way. If a last review-N.md exists, add `## Applied (user instructions)` at its end.
- Fix build.py and run it again. Do not rewrite it from scratch. Fix outline.md too if needed.
- Add an `## Applied` section at the end of review-N.md, with one line per rule ID saying what you fixed.
