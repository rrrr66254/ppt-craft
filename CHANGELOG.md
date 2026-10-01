# Changelog

## 0.2.0

Imagery
- Placement patterns built per slide from its content: `bleed-panel`, `bleed-scrim`, `split` (half-bleed), `inset`, `strip`, `gallery` (with an optional hero image), plus `figure`, `annotated` and `type-only`. `deckkit.patterns.suggest()` ranks them from the image, the slide's role and the previous slides.
- Text over photos is checked for contrast: the solid scrim is planned from the photo's pixels and falls back to a solid panel when it cannot reach the target. Panels and scrims keep clear of the image focus.
- Photo treatments, one per deck: none, harmonize, gray, duotone (`imagefx.py treat`).
- Optional generated texture (paper, grain, dots, grid) for one cover or section slide (`imagefx.py texture`, `Deck.texture`).
- `imagefx.py compare`: one rendered sheet of your own photo across treatments and placements, used in the style stage.
- `imagery` section in `style.json` (allowed patterns, treatment, harmonize, texture, `max_bleed`); presets set their own.
- Sample decks can include an image slide.

Lint
- New rules: L24 (too many full-bleed slides), C13 (texture misuse), L19 (crowded image slides), L23 (more than 5 bullets), C12 (pure black text), W15 (straight quotes in English decks), W16 (fake names). L2 also catches the same image pattern on 3 slides in a row.

Other
- Fixes: footer stays on the text side of a split photo, contained images sit on the grid edge, `"\v"` is a line break inside a paragraph.
- Examples: business report, conference talk, research talk, style candidates and image patterns (`examples/`).
- Usage guides in English and Korean (`docs/USAGE.md`, `docs/USAGE.ko.md`).

## 0.1.0

Initial release: brief interview, three rendered style candidates from references or presets, font comparison and per-user font install, outline and `deckkit` build to an editable `.pptx`, text/XML lint, and a capture-based reviewer loop. Optional photos, generated images and icons with recorded credits.
