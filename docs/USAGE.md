# ppt-craft usage guide

[한국어](USAGE.ko.md)

- [Install](#install)
- [Quick start](#quick-start)
- [The workflow](#the-workflow)
- [Giving references](#giving-references)
- [Content input and use cases](#content-input-and-use-cases)
- [Fonts](#fonts)
- [Images and placement](#images-and-placement)
- [Reviewing an existing deck](#reviewing-an-existing-deck)
- [Editing afterwards](#editing-afterwards)
- [Examples](#examples)
- [FAQ and troubleshooting](#faq-and-troubleshooting)

## Install

### From the shell

```bash
claude plugin marketplace add rrrr66254/ppt-craft
claude plugin install ppt-craft@ppt-craft
```

The plugin is installed for your user (scope `user`) by default.

### Inside a Claude Code session

```
/plugin marketplace add rrrr66254/ppt-craft
/plugin install ppt-craft@ppt-craft
```

The second command opens the plugin's details in the `/plugin` panel, where you confirm the install.

After installing, run `/reload-plugins` or restart Claude Code.

### Check that it worked

```bash
claude plugin list
claude plugin details ppt-craft
```

`claude plugin list` shows `ppt-craft@ppt-craft` with Status `enabled`. `claude plugin details ppt-craft` lists Skills (5): `deck`, `deck-brief`, `deck-build`, `deck-review`, `deck-style`, and Agents (1): `deck-reviewer`.

### Pin a version

Add the marketplace at a git tag:

```bash
claude plugin marketplace add rrrr66254/ppt-craft#v0.2.1
```

### Install for a whole team or repository

Run this once in the repository:

```bash
claude plugin marketplace add rrrr66254/ppt-craft --scope project
```

It writes `.claude/settings.json`. Commit that file. Teammates get the marketplace after they trust the folder in Claude Code.

### Updates

Background auto-update is off by default for third-party marketplaces like this one. Either:

- turn it on: `/plugin` → Marketplaces → ppt-craft → Enable auto-update, or
- update by hand: `/plugin marketplace update ppt-craft` in a session, or `claude plugin update ppt-craft@ppt-craft` in the shell.

You get a new copy only when the plugin's version number changes. Restart Claude Code after an update.

### Try it from a clone without installing

```bash
git clone https://github.com/rrrr66254/ppt-craft
claude --plugin-dir ./ppt-craft
```

### Uninstall

```bash
claude plugin uninstall ppt-craft@ppt-craft
claude plugin marketplace remove ppt-craft
```

The first removes the plugin. The second removes the marketplace and uninstalls its plugins. Uninstalling also deletes the plugin's data folder (remembered fonts and saved styles, see [Fonts](#fonts)); pass `--keep-data` to `uninstall` to keep it.

### Requirements

- **Python 3.10 or newer.** The skills run `python`, or `python3` if `python` is missing.
- **Python packages:** python-pptx, Pillow, resvg-py (`requirements.txt`). When a script fails with `ModuleNotFoundError`, Claude asks for your consent and runs `pip install -r "<plugin folder>/requirements.txt"`. To do it yourself, install into the same Python that `python` runs:

  ```bash
  python -m pip install -r ~/.claude/plugins/cache/ppt-craft/ppt-craft/<version>/requirements.txt
  ```

  The installed copy lives at `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` (on Windows, `%USERPROFILE%\.claude\plugins\cache\ppt-craft\ppt-craft\<version>\`). From a clone, use the clone's `requirements.txt`.
- **A renderer.** Style candidates and review need rendered slide images. A new deck checks this before the interview starts and stops with install instructions if none is found.
  - Windows: Microsoft PowerPoint, used automatically when installed.
  - Otherwise (and on macOS and Linux): LibreOffice plus a PDF-to-PNG converter, either poppler (`pdftoppm`) or `pip install pymupdf`.
    - macOS: `brew install --cask libreoffice && brew install poppler`
    - Linux: `sudo apt install libreoffice poppler-utils`

  Check with `python "<plugin folder>/scripts/render.py" --check`. It prints `powerpoint` or `libreoffice`, or exits with code 2 and the install instructions.

### Install troubleshooting

- The marketplace is cloned with your own `git`. For `owner/repo` sources, Claude Code tries SSH first and falls back to HTTPS. Set `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1` to skip the SSH attempt (useful when SSH to GitHub hangs or is blocked).
- Skills do not show up after install: run `/reload-plugins` or restart, then check `claude plugin details ppt-craft`.

## Quick start

Start with the `/ppt-craft:deck` command or just ask. Some starting points:

**Topic only**

```
/ppt-craft:deck a 10-minute internal talk on why we moved session storage to Redis
```
```
/ppt-craft:deck 신입 개발자 대상 사내 코드 리뷰 문화 소개, 15분
```

**From a document**

```
/ppt-craft:deck make a 12-slide board update from ./q3-report.pdf
```
```
./연구노트.md 내용으로 랩미팅 발표자료 만들어줘. 20분.
```

**From your own outline**

```
Build a deck from this outline, keep my order:
1. Checkout p99 doubled after the September release
2. The cause is the new fraud check running inline
3. Moving it async brings p99 back to 410ms
4. Ask: approve two days of work next sprint
```
```
이 목차대로 PPT 만들어줘: 1) 현황 2) 문제 3) 원인 4) 제안 5) 일정
```

Claude replies in the language you write in, and the deck is built in the deck's language (Korean or English).

## The workflow

All work happens in `decks/<slug>/` under your current folder. The slug is a short English kebab-case name for the topic (for example `decks/redis-sessions/`). Every stage reads and writes files there, so you can stop at any point.

### 1. Brief

Claude asks only what it does not already know from your message:

- audience and goal (what the audience should do afterwards)
- length (slides or minutes; minutes are converted at about one slide per minute)
- content source: topic only, materials (a path), or an outline
- references and images (including a logo)
- optional: date, event, presenter name, voice, a sample of your writing

If you only give a topic, it asks for the facts to use: figures, dates, names, real examples. If you have none, the brief records `lack of factual material`, and later stages do not invent facts to fill the gap.

File: `brief.md`.

### 2. Style

Claude builds three style candidates, renders a sample deck for each from your brief's real content, and shows you one comparison image (`candidates/compare.png`). You pick one, or ask for a mix ("A's colors with B's layout"), which is rendered as a fourth candidate.

Then the details, each shown as a re-rendered sample:

1. **Fonts.** 2-3 font candidates rendered side by side. See [Fonts](#fonts).
2. **Color, cover, structure.** Only if you want changes: cover type (type, band, image), structure (assertion titles, or a governing message under each title for reports), default body layout (split, statement, figure).
3. **Logo and footer.** The event name and page number are in the footer by default.
4. **Imagery** (only when the deck uses photos). One comparison of your own photo: four treatments (none, harmonize, gray, duotone) and three placements (bleed-panel, bleed-scrim, split). See [Images and placement](#images-and-placement).

Files while this runs: `candidates/A`, `B`, `C` (each with `style.json`, `sample.pptx`, `renders/`), `candidates/sample.json`, `candidates/compare.png`, font comparisons in `candidates/F1`, `F2`, ..., and `candidates/imagery/`. When the style is final, `style.json` is saved and `candidates/` is deleted.

You never see raw `style.json`; every choice is made from rendered images.

### 3. Outline and build

First a storyboard: the one-line thesis and the slide titles only. Titles are claim sentences, and read in order they make the argument. With a topic only, Claude asks you to confirm the storyboard. With your own outline, it keeps your order and tells you where it reworded a title into a claim.

Then a per-slide table in `outline.md`: title, supporting content, visualization type (one sentence, big number, chart, comparison table, 2x2, process, full-bleed image, quote, diagram, annotated screenshot), assets, image placement and why, speaker notes, and figure source.

Then Claude writes `build.py` (using the bundled `deckkit` library), runs it, and fixes every build warning (text overflow, mid-word breaks, missing fonts, low image resolution, and so on).

Files: `outline.md`, `assets/` (prepared images, `images.json`, `treated/`, `icons/`, `credits.json`), `build.py`, `out.pptx`.

### 4. Lint and review

1. `lint.py` checks the text and XML for AI tells (writes `lint.json`).
2. `render.py` renders every slide (`renders/slide-01.png`, ..., `renders/sheet.png`).
3. A separate `deck-reviewer` agent judges the deck from the renders, the brief, the style and the outline. It never sees `build.py` or earlier reviews.
4. The result is `review-N.md`. Its first line is `RESULT: PASS` or `RESULT: FAIL`.

On FAIL, Claude fixes every blocker and major in `build.py`, records what it changed under `## Applied` in that review file, rebuilds, and reviews again. The review runs at most 3 times. If the third is still FAIL, you choose: accept as is, drop the affected slide, or give your own instructions.

### 5. Wrap-up

After PASS, Claude reports the path and slide count, the chosen style, any remaining minor issues, and the slide numbers still marked `[source needed]` (`[출처 필요]` in Korean decks). It deletes the working files (`renders/`, `candidates/`, `assets/_cand/`, `lint.json`) and keeps `brief.md`, `style.json`, `outline.md`, `build.py`, `out.pptx`, `assets/` and `review-*.md`.

### Resuming

```
/ppt-craft:deck decks/<slug>
```

Claude looks at which files exist and continues from the next stage. Asking for changes after a PASS sends the deck back through build and review.

### Running one stage

The stage skills take the deck folder as their argument:

```
/ppt-craft:deck-brief decks/<slug>
/ppt-craft:deck-style decks/<slug>
/ppt-craft:deck-build decks/<slug>
/ppt-craft:deck-review decks/<slug>
```

`deck-style` needs `brief.md`; `deck-build` needs `brief.md` and `style.json`. Normally `/ppt-craft:deck` runs them in order.

## Giving references

Mention references when Claude asks, or in your first message. Only visual attributes are taken: color, typography, grid, margins, motifs. Logos, illustrations, photos and template files are never copied.

| Reference | What happens |
|---|---|
| `.pptx` file | Colors, fonts, sizes and margins are read from the file; the slides are rendered so Claude can see the layout and motifs |
| Image (screenshot, photo of a slide) | Claude looks at it and notes colors (estimated hex), type family, grid, margins, motifs |
| URL | Captured with a browser tool if available, otherwise colors and fonts are read from the page's HTML/CSS |
| SlidesCarnival, Slidesgo or Microsoft Create theme page | Only the single page you give is opened; no searching, crawling or downloading |
| Canva, Miricanvas, Mangoboard, Google Slides templates | Not accessed automatically (terms of service). Send a screenshot instead |
| "Find one on the web" | A web search, opening only the sites above. Falls back to presets if that fails |

With a reference, the three candidates are: A, a faithful reproduction; B, refined, with the reference's own AI tells removed; C, a bold variation with the same feel.

Without a reference, three built-in presets are the starting point, adjusted to your brief:

| Preset | For |
|---|---|
| `report-grid` | Korean corporate report convention (title / governing message / body). Business, internal reports, proposals |
| `keynote-type` | One sentence per slide in big type. Tech talks, conferences, keynotes |
| `academic-figure` | Figures and tables are the stars. Research talks, paper presentations, lab meetings |

If you plan to use a downloaded template file yourself, keep its terms: Slidesgo free keeps its credits slide, SlidesCarnival needs attribution and a link, Mangoboard free keeps its watermark.

To reuse a style later, say "save this style". It is stored in the plugin's data folder and offered as a candidate next time.

## Content input and use cases

| You give | What Claude does |
|---|---|
| A topic only | Asks for the facts per slide, then proposes a storyboard for you to confirm |
| Documents (PDF, Markdown, notes) | Reads them and pulls out claims, figures with their source (file, page, URL), names and examples |
| Your own outline | Keeps your order and structure; only rewords titles into claims and says so |

Figures are copied exactly from your materials. A figure with no source is left as `[source needed]` on the slide so you can fill it in; nothing is made up. Each slide with a figure also gets a small source line.

Typical uses:

- **Tech talk or conference:** `keynote-type`, one claim per slide, big numbers as scale breaks, annotated screenshots instead of device mockups.
- **Academic or lab meeting:** `academic-figure`, numbered figures with captions, charts with axes, units and sample size (`n`, only when your materials give it).
- **Business report or proposal:** `report-grid` with `governing` structure: a title plus one governing sentence per slide, ending on a decision or request.
- **Lecture or training:** any preset; mix dense reference slides with one-sentence slides, and put what you would say in the speaker notes.

## Fonts

- Claude asks once and remembers your choice in `prefs.json` in the plugin's data folder (`~/.claude/plugins/data/ppt-craft-ppt-craft/`). Next time it suggests the same fonts first.
- Candidates are rendered side by side on your sample slides. Overused defaults (Inter, Roboto, Arial, Poppins, Montserrat, Calibri, Malgun Gothic and others) are left out unless you name one.
- Korean decks only offer fonts with Hangul glyphs.
- A free-font catalog (`data/fonts.json`) mixes installed and not-installed picks, for example Pretendard, Wanted Sans, SUIT, IBM Plex Sans KR, Nanum Myeongjo, Gowun Batang, JetBrains Mono, Source Serif 4. A not-installed font is downloaded (with your consent) and installed **for your user only, without admin rights**:
  - Windows: `%LOCALAPPDATA%\Microsoft\Windows\Fonts`
  - macOS: `~/Library/Fonts`
  - Linux: `~/.local/share/fonts`
- Restart PowerPoint after a font is installed.
- Some catalog fonts (Gmarket Sans, LINE Seed Sans KR, Paperlogy, NanumSquare Neo) are marked `manual`: Claude gives you the official download page instead.
- Fonts are not embedded automatically. If the people you send the deck to may not have the font, turn on File > Options > Save > "Embed fonts in the file" in PowerPoint and save.

## Images and placement

### Where images come from

1. Your own images first (photos, screenshots, diagrams, logos). Mark a logo in the brief; it goes in the same place on every body slide.
2. Optionally, with your consent: free photos or AI-generated images, as equal options.
3. Otherwise no image. A slide without an image is always allowed; an image goes in only when it proves the slide's point.

Your originals are not modified. Copies with EXIF rotation applied and the long edge at most 3000 px go into `assets/`.

### Placement patterns

Each image slide gets one pattern, picked from the slide's content and the image, and written in the outline with a reason:

| Pattern | Used for |
|---|---|
| `bleed-panel` | Full-bleed photo with a solid panel for the text |
| `bleed-scrim` | Full-bleed photo with a solid translucent band, contrast-checked; falls back to `bleed-panel` when contrast fails or there are more than 15 words |
| `split` | Half-bleed photo beside the text (default 5:7 image:text, 7:5 when the photo is the point) |
| `inset` | Captioned photo inside the content area |
| `strip` | Panorama band (3:1 or wider) |
| `gallery` | 2-4 comparable images, optionally one large "hero" |
| `figure` | Diagram or logo, contained, with a caption |
| `annotated` | Screenshot with callouts pointing at what matters |
| `type-only` | No image |

Rules that apply everywhere: at most `max_bleed` full-bleed slides (3 by default), never the same pattern 3 slides in a row, text placed opposite the image's focus, solid scrims only (never gradients), no fake device frames or shape masks.

### Treatments and texture

- One treatment for every photo in the deck: `none`, `gray` or `duotone` (from the style's ink and background colors). `harmonize`, a slight desaturation so photos from different sources sit together, is on by default. You choose from the rendered comparison.
- Texture (paper, grain, dots, grid) only if you ask, at 0.1 opacity or less, on one cover or section slide.

### Focus, captions and credits

- Claude marks each image's focus (the area that must stay visible) and anything that must not be cropped (faces, text). Crops are placed around that.
- Every photo and figure gets a caption with provenance (source, date, place). Without one, the slide shows `[source needed]`.
- Licenses for fetched images are recorded in `assets/credits.json`. Credit lines go in the speaker notes of the slide that uses the image, and images that require attribution, are share-alike, or are AI-generated are also listed on a small credits slide at the end.

### Optional free assets

Nothing is fetched until you agree. Claude asks once per session and names what goes where:

- photos: Openverse, Wikimedia Commons (no key); Pexels, Pixabay (free key)
- AI images: Cloudflare Workers AI, Pollinations, Hugging Face (key), otherwise the volunteer-run AI Horde (no key, small images up to 576 px)
- icons: Iconify, permissive licenses only (MIT, ISC, Apache-2.0), one icon set per deck
- fonts: Google Fonts, GitHub

If you decline, only your own images and installed fonts are used, and no icons.

### API keys

All keys are optional and free to get. Set them as environment variables, then restart Claude Code.

| Variable | Used for |
|---|---|
| `PEXELS_API_KEY` | Pexels photo search |
| `PIXABAY_API_KEY` | Pixabay photo search |
| `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` | Image generation with FLUX.1-schnell (free tier; larger images than AI Horde) |
| `POLLINATIONS_API_KEY` | Image generation |
| `HF_TOKEN` | Image generation via Hugging Face (small free credit) |

Never paste keys into the chat. The scripts only report whether a key was found, never its value.

### Privacy

When you allow network use, your search words and image prompts are sent to the services above. Claude keeps confidential text from your brief out of them, but check before you agree if the topic itself is sensitive. Without keys, prompts go to AI Horde, which is run by volunteers.

## Reviewing an existing deck

```
/ppt-craft:deck-review path/to/file.pptx
```

Or ask "review my PPT" / "AI 티 나는지 봐줘". Output goes to `<file name>-review/` next to the file: `lint.json`, `renders/`, and `review-1.md`. Your file is rendered from a temporary copy, so it is safe to keep it open in PowerPoint. The file itself is never changed. If you want it redone, Claude can build a new deck with `/ppt-craft:deck`, using your file as a reference.

**Lint** (automatic, from text and XML):

- text: leftover placeholders, emoji, stock AI phrases and translationese (English and Korean word lists), em dashes, colon and Title Case titles, "Thank you" / "Q&A" style titles, figures without a source, fake names (John Doe, Acme), straight quotes in English decks, rule-of-three bullets, more than 5 bullets in a list
- fonts: no East Asian font on Hangul (substitution), Hangul runs without `lang="ko-KR"` (mid-word breaks), overused default fonts
- shapes and color: gradients, shadows, accent rules under titles, stripes on cards, bar charts drawn with shapes, pure black text, too many colors on one slide
- imagery: more full-bleed slides than `max_bleed`, the same layout or pattern 3 slides in a row, crowded image slides, texture on more than one slide

**Reviewer** (from the renders): clipped or overlapping text, font substitution, layout repetition and rhythm, card grids, center-aligned everything, contrast and text size, whether the titles alone carry the argument, whether figures show their source, chart axes and units, speaker notes, crops and image quality, text legibility over photos, consistent photo treatment, captions, and the human signals (specific facts, real names, annotations, varied density).

Rule IDs and descriptions are in [`rules/tells.md`](../rules/tells.md).

| Severity | Meaning |
|---|---|
| blocker | Must not ship as is (for example a leftover placeholder, emoji, no East Asian font) |
| major | A clear AI tell or a readability problem |
| minor | Worth polishing |

`RESULT: PASS` means no blockers and no majors. Every finding has a rule ID and a concrete fix (which column, which sentence).

## Editing afterwards

Everything in `out.pptx` is native and editable in PowerPoint:

- **Text** is in normal text boxes and title placeholders, with real paragraph bullets.
- **Charts** are native PowerPoint charts. Right-click > Edit Data to change the numbers.
- **Photos** use native crops; the full original is kept inside the file. Use Picture Format > Crop to re-crop.
- **Icons** are SVG: editable vectors in PowerPoint 2019 and 365 (with a PNG fallback in older versions).
- **Scrims and panels** are plain shapes with a solid fill and transparency.
- **Speaker notes** are filled in.

Two ways to change a deck:

- Ask Claude: `/ppt-craft:deck decks/<slug>` plus what you want changed. It edits `build.py`, rebuilds, and reviews again.
- Edit `out.pptx` in PowerPoint yourself. Note that rebuilding from `build.py` overwrites `out.pptx`, so save hand edits under a different name, or make them after you are done with Claude.

## Examples

The examples are fictional sample content, and no photos are included. Each folder has the `build.py` and `style.json` that produced its contact sheet.

| Example | Contact sheet | Source |
|---|---|---|
| Business report | [sheet.jpg](../examples/business-report/sheet.jpg) | [build.py](../examples/business-report/build.py), [style.json](../examples/business-report/style.json) |
| Conference talk | [sheet.jpg](../examples/conference-talk/sheet.jpg) | [build.py](../examples/conference-talk/build.py), [style.json](../examples/conference-talk/style.json) |
| Research talk | [sheet.jpg](../examples/research-talk/sheet.jpg) | [build.py](../examples/research-talk/build.py), [style.json](../examples/research-talk/style.json) |

Also: [style candidates](../examples/style-candidates.jpg) as shown during the style stage, and [image placement patterns](../examples/image-patterns.jpg).

## FAQ and troubleshooting

**"No renderer" / render exits with code 2.**
Install PowerPoint (Windows) or LibreOffice plus poppler or pymupdf (see [Requirements](#requirements)), then run `render.py --check`. Review never runs without renders. Note that LibreOffice drops hidden slides when converting.

**`ModuleNotFoundError`.**
The Python packages are missing from the Python that runs `python`. Let Claude install them, or run `python -m pip install -r "<plugin folder>/requirements.txt"`.

**A font is not installed / text shows in Malgun Gothic or Gulim.**
The build warns `Font '…' is not installed` and stops to ask whether to install it or switch fonts. After installing, restart PowerPoint. If `fonts.py install` fails because Python comes from the Microsoft Store (it cannot write fonts there), install the font file yourself from the official link Claude gives. For recipients, embed fonts (File > Options > Save).

**PowerPoint is busy or the render hangs.**
Rendering on Windows drives PowerPoint in the background. It opens a temporary copy and only quits PowerPoint if it started it and no window is open. An open dialog in PowerPoint (save prompt, sign-in, update) can block the export; close it and try again. A render that runs past 15 minutes is stopped. If PowerPoint keeps getting in the way, install LibreOffice and pass `--backend libreoffice` to `render.py`.

**Korean words break in the middle of a line.**
PowerPoint breaks Hangul mid-word unless the text is tagged as Korean. ppt-craft sets `lang="ko-KR"` on every Hangul run, and lint flags any run without it (T11). For text you add by hand in PowerPoint, select it and set Review > Language to Korean.

**Network was declined; can I still get images?**
Yes, your own images. Add their paths in the brief or tell Claude. Icons and catalog fonts need the network.

**A fetched image is too small.**
`photo get` warns when an image is narrow (`low_res`); it is kept to small slots. Keyless AI Horde images are 576 px at most. Set `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` for larger generated images.

**Can I stop halfway?**
Yes. Everything is in `decks/<slug>/`. Resume with `/ppt-craft:deck decks/<slug>`.
